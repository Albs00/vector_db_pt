#!/usr/bin/env python3
"""Permanent offline production tests and certification for PT26 CLIMA.

Run: python tests/test_clima_master_production.py
Re-certify a freshly built release: add --certify
No runtime, catalogue extraction, semantic matching, downloads or network calls.
The reversible audit recipe permits re-building from the exact input bytes even
when the original filenames were renamed by a download manager.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get('CLIMA_RELEASE_ROOT', Path(__file__).resolve().parents[1]))
TOOLS = ROOT/'tools'/'promote_clima_master.py'
sp = importlib.util.spec_from_file_location('promotion', TOOLS)
P = importlib.util.module_from_spec(sp); sp.loader.exec_module(P)
CERTIFY = '--certify' in sys.argv


def load(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('Duplicate JSON object key: '+k)
            d[k]=v
        return d
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite '+x)))


def input_recipes(root):
    f=root/'reports/clima_master_production_audit.json'
    return load(f if f.exists() else root/'reports/promotion_build_seed.json')


def pt_set(d):return {p['pt'] for p in d['products']}


def config_key(scope,ue,ui):return scope+'|'+ue+'|'+','.join(sorted(ui))


def expand_rule(rule):
    """Independent multiset enumeration; never reads btu_match/derived values."""
    values={}
    for capacity,pool in rule['ui_by_capacity'].items():
        for pt in pool:
            if pt in values and values[pt]!=int(capacity):raise ValueError('PT in different capacity pools')
            values[pt]=int(capacity)
    allowed={tuple(sorted(x)) for x in rule['allowed_multisets']}
    out=set()
    for n in sorted({len(x) for x in allowed}):
        for combo in itertools.combinations_with_replacement(sorted(values),n):
            if tuple(sorted(values[pt] for pt in combo)) in allowed:out.add(combo)
    return out


def independent_indices(d):
    maps={}
    def build(rows, fn):
        a=defaultdict(set)
        for i,r in enumerate(rows):
            v=fn(r)
            if not isinstance(v,(set,list,tuple)):v=[v]
            for k in v:
                if k is not None and k!='':a[str(k)].add(i)
        return {k:sorted(a[k]) for k in sorted(a)}
    maps['index_by_pt']=build(d['products'],lambda p:p['pt'])
    maps['index_by_model']=build(d['products'],lambda p:{P.normalized_model(s) for s in [p['model']]+p.get('model_aliases',[])})
    multi='systems' in d;rows=d['ui_catalog'] if multi else d['pairs']
    cap=lambda r:r if multi else r['ui_capacity']
    maps['index_by_ui_btu']=build(rows,lambda r:cap(r).get('btu_match'))
    maps['index_by_kw']=build(rows,lambda r:cap(r).get('cooling_kw'))
    maps['capacity_lookup']={str(i):{'cooling_kw':cap(r).get('cooling_kw'),'btu_from_kw_raw':cap(r).get('btu_from_kw_raw')}
                             for i,r in enumerate(rows) if cap(r).get('btu_match_source')=='DERIVED_RAW_KW'}
    maps['index_by_family']=build(rows,lambda r:r.get('family'))
    maps['index_by_ue_pt']=build(d['systems'] if multi else rows,lambda r:r['ue_pt'])
    if multi:
        maps['index_systems_by_family']=build(d['systems'],lambda r:r.get('family'))
        maps['index_combinations_by_ue_pt']=build(d['combination_master'],lambda r:r['ue_pt'])
        maps['index_by_configuration_key']={r['configuration_key']:i for i,r in enumerate(d['combination_master'])}
    else:maps['index_by_configuration_key']=build(d['combination_master'],lambda r:r['configuration_key'])
    return maps


def inspect_references(kind,d):
    issues=[];products=d['products'];n=len(products)
    def issue(code,path,detail):issues.append({'code':code,'dataset':kind,'path':path,'detail':detail})
    def lookup(idx,pt,role,scope,brand,path):
        if not isinstance(idx,int) or isinstance(idx,bool) or not 0<=idx<n:
            issue('INVALID_REFERENCE',path,str(idx));return None
        p=products[idx]
        if p['pt']!=pt:issue('REFERENCE_PT_MISMATCH',path,f'{pt} -> {p["pt"]}')
        if p['role']!=role:issue('ROLE_MISMATCH',path,f'{role} -> {p["role"]}')
        if p['scope']!=scope:issue('SCOPE_LEAK',path,f'{scope} -> {p["scope"]}')
        if brand is not None and p['brand']!=brand:issue('CROSS_BRAND',path,f'{brand} -> {p["brand"]}')
        return p
    if 'pairs' in d:
        for i,r in enumerate(d['pairs']):
            for side,role in [('ui','UI'),('ue','UE')]:
                lookup(r[side+'_product_id'],r[side+'_pt'],role,r['scope'],r['brand'],f'/pairs/{i}/{side}')
        for i,r in enumerate(d['other_systems']):
            if not 0<=r['product_id']<n:issue('INVALID_REFERENCE',f'/other_systems/{i}',str(r['product_id']));continue
            p=products[r['product_id']]
            lookup(r['product_id'],r['pt'],p['role'],r['scope'],None,f'/other_systems/{i}')
    else:
        for i,c in enumerate(d['ui_catalog']):lookup(c['product_id'],c['pt'],'UI',c['scope'],None,f'/ui_catalog/{i}')
        for i,c in enumerate(d['component_catalog']):lookup(c['product_id'],c['pt'],'ACCUMULO_ACS',c['scope'],None,f'/component_catalog/{i}')
        for i,s in enumerate(d['systems']):
            lookup(s['ue_product_id'],s['ue_pt'],'UE',s['scope'],s['brand'],f'/systems/{i}/ue')
            for j,e in enumerate(s['allowed_ui']):
                cidx=e['ui_context_id'];path=f'/systems/{i}/allowed_ui/{j}'
                if not isinstance(cidx,int) or not 0<=cidx<len(d['ui_catalog']):issue('INVALID_REFERENCE',path,str(cidx));continue
                c=d['ui_catalog'][cidx]
                if c['pt']!=e['pt']:issue('REFERENCE_PT_MISMATCH',path,'context PT')
                if c['scope']!=s['scope']:issue('SCOPE_LEAK',path,'UI context / system')
                lookup(c['product_id'],e['pt'],'UI',s['scope'],s['brand'],path)
            allowed={e['pt'] for e in s['allowed_ui'] if e['status']=='CONFIRMED'}
            for j,combo in enumerate(s['explicit_combinations']):
                for pt in combo:
                    if pt not in allowed:issue('UNKNOWN_AUTHORIZED_POOL_MEMBER',f'/systems/{i}/explicit_combinations/{j}',pt)
            for rule in s['configuration_rules']:
                for pool in rule['ui_by_capacity'].values():
                    for pt in pool:
                        found=[p for p in products if p['pt']==pt and p['role']=='UI' and p['scope']==s['scope'] and p['brand']==s['brand']]
                        if not found:issue('INVALID_RULE_PT',f'/systems/{i}/rules/{rule["id"]}',pt)
                        if rule['status']=='CONFIRMED' and pt not in allowed:issue('UNKNOWN_AUTHORIZED_POOL_MEMBER',f'/systems/{i}/rules/{rule["id"]}',pt)
    return issues


def inspect_configurations(kind,d):
    issues=[]
    def fail(code,i,detail):issues.append({'code':code,'dataset':kind,'path':f'/combination_master/{i}','detail':detail})
    if kind=='monosplit':
        for i,c in enumerate(d['combination_master']):
            ix=c['pair_id']
            if not isinstance(ix,int) or not 0<=ix<len(d['pairs']):fail('INVALID_REFERENCE',i,'pair_id');continue
            p=d['pairs'][ix]
            for f in ['scope','ui_pt','ue_pt','family','status','provenance','source']:
                if c[f]!=p[f]:fail('PAIR_MASTER_MISMATCH',i,f)
            if c['ui_btu_match']!=p['ui_capacity']['btu_match']:fail('PAIR_CAPACITY_MISMATCH',i,'btu')
            if c['configuration_key']!='MONOSPLIT|'+p['ui_pt']+'|'+p['ue_pt']:fail('INVALID_CONFIGURATION_KEY',i,c['configuration_key'])
        if Counter(c['pair_id'] for c in d['combination_master'])!=Counter(range(len(d['pairs']))):
            fail('MISSING_OR_DUPLICATED_CONTEXT',0,'pairs not represented exactly once')
        return issues
    rule_cache={}
    for i,c in enumerate(d['combination_master']):
        si=c['system_id']
        if not isinstance(si,int) or not 0<=si<len(d['systems']):fail('INVALID_REFERENCE',i,'system_id');continue
        s=d['systems'][si]
        if c['ue_pt']!=s['ue_pt']:fail('WRONG_UE',i,c['ue_pt'])
        if c['scope']!=s['scope']:fail('SCOPE_LEAK',i,c['scope'])
        if c['status']!='CONFIRMED':fail('UNCONFIRMED_MASTER_ENTRY',i,c['status'])
        if s['evidence'] in ('PAIRWISE_ONLY','NOT_CONFIRMED'):fail('UNAUTHORIZED_COMBINATION',i,s['evidence'])
        if c['configuration_key']!=config_key(c['scope'],c['ue_pt'],c['ui_pts']):fail('INVALID_CONFIGURATION_KEY',i,c['configuration_key'])
        if c['ui_pts']!=sorted(c['ui_pts']):fail('NONCANONICAL_MULTISET',i,'order')
        if c['ui_count']!=len(c['ui_pts']):fail('QUANTITY_MISMATCH',i,'ui_count')
        if len(c['capacity_signature'])!=len(c['ui_pts']):fail('QUANTITY_MISMATCH',i,'capacity_signature')
        if s['min_ui'] is not None and c['ui_count']<s['min_ui']:fail('UI_COUNT_BOUND',i,'below source minimum')
        if s['max_ui'] is not None and c['ui_count']>s['max_ui']:fail('UI_COUNT_BOUND',i,'above source maximum')
        confirmed_edges={x['pt'] for x in s['allowed_ui'] if x['status']=='CONFIRMED'}
        if not set(c['ui_pts'])<=confirmed_edges:fail('UNAUTHORIZED_POOL',i,'not in confirmed edges')
        if 'rule_id' in c:
            rules=[r for r in s['configuration_rules'] if r['id']==c['rule_id']]
            if len(rules)!=1 or rules[0]['status']!='CONFIRMED':fail('UNAUTHORIZED_RULE',i,c['rule_id']);continue
            r=rules[0];rk=(si,r['id'])
            if rk not in rule_cache:rule_cache[rk]=expand_rule(r)
            if tuple(c['ui_pts']) not in rule_cache[rk]:fail('UNAUTHORIZED_COMBINATION',i,'not generated by exact pool rule')
            if c['provenance']!=r['provenance']:fail('WRONG_PROVENANCE',i,'rule')
            caps={pt:int(k) for k,pts in r['ui_by_capacity'].items() for pt in pts}
            if c['capacity_signature']!=sorted(caps[pt] for pt in c['ui_pts']):fail('WRONG_CAPACITY_SIGNATURE',i,r['id'])
        else:
            if tuple(c['ui_pts']) not in {tuple(sorted(x)) for x in s['explicit_combinations']}:fail('UNAUTHORIZED_COMBINATION',i,'not explicit')
            if c['provenance']!=s['explicit_combinations_provenance']:fail('WRONG_PROVENANCE',i,'explicit')
            if c['source']!=s['explicit_combinations_source']:fail('WRONG_SOURCE',i,'explicit')
    return issues


class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ROOT;cls.recipe=input_recipes(ROOT)
        cls.docs={k:load(ROOT/'Knowledge'/P.OUTPUT_NAME[k]) for k in P.KINDS}
        cls.manual=load(ROOT/'Knowledge/manual_overrides_clima.json')
        cls.originals={k:P.reconstruct_original(d,cls.recipe['migrations'][k]) for k,d in cls.docs.items()}
        cls.refs={k:inspect_references(k,d) for k,d in cls.docs.items()}
        cls.configs={k:inspect_configurations(k,d) for k,d in cls.docs.items()}
        cls.determinism_result=None
    def test_001_json_parse_and_no_duplicate_object_keys(self):
        for d in self.docs.values():self.assertIsInstance(d,dict)
    def test_002_schema_still_3_0_0(self):
        for d in self.docs.values():self.assertEqual(d['schema_version'],'3.0.0')
    def test_003_release_metadata_and_fail_closed(self):
        for d in self.docs.values():
            self.assertEqual(d['dataset_version'],P.DATASET_VERSION);self.assertEqual(d['production_policy'],'FAIL_CLOSED')
            self.assertEqual(d['release_status'],'PRODUCTION_MASTER')
    def test_004_all_original_top_level_sections_preserved(self):
        for k,d in self.docs.items():self.assertTrue(set(self.originals[k])<=set(d))
    def test_005_original_bytes_reconstruct_exactly(self):
        for k,d in self.originals.items():
            self.assertEqual(hashlib.sha256(P.serialize(d)).hexdigest(),self.recipe['build_spec']['inputs'][k]['sha256'])
            self.assertEqual(P.semantic_sha(d),self.recipe['build_spec']['inputs'][k]['semantic_sha256'])
    def test_006_no_principal_pt_lost(self):
        for k,d in self.docs.items():self.assertFalse(pt_set(self.originals[k])-pt_set(d))
    def test_007_no_principal_pt_invented(self):
        for k,d in self.docs.items():self.assertFalse(pt_set(d)-pt_set(self.originals[k]))
    def test_008_principal_union_2039(self):self.assertEqual(len(set.union(*(pt_set(d) for d in self.docs.values()))),2039)
    def test_009_pt_string_eight_digits(self):
        for d in self.docs.values():
            for p in d['products']:self.assertIsInstance(p['pt'],str);self.assertRegex(p['pt'],r'^\d{8}$')
            for c in d['combination_master']:
                for pt in [c['ue_pt']]+c.get('ui_pts',[c.get('ui_pt')]):self.assertRegex(pt,r'^\d{8}$')
    def test_010_product_reference_integrity(self):
        for issues in self.refs.values():self.assertFalse([x for x in issues if x['code'] in ('INVALID_REFERENCE','REFERENCE_PT_MISMATCH')],issues[:10])
    def test_011_role_integrity(self):
        for issues in self.refs.values():self.assertFalse([x for x in issues if x['code']=='ROLE_MISMATCH'],issues[:10])
    def test_012_scope_integrity(self):
        for issues in self.refs.values():self.assertFalse([x for x in issues if x['code']=='SCOPE_LEAK'],issues[:10])
    def test_013_brand_integrity(self):
        for issues in self.refs.values():self.assertFalse([x for x in issues if x['code']=='CROSS_BRAND'],issues[:10])
    def test_014_all_reference_checks(self):
        for issues in self.refs.values():self.assertEqual(issues,[])
    def test_015_only_expected_main_roles(self):
        for d in self.docs.values():self.assertTrue({p['role'] for p in d['products']} <= {'UI','UE','PRODOTTO_AUTONOMO','ACCUMULO_ACS'})
    def test_016_no_new_accessory_objects_or_roles(self):
        for k,d in self.docs.items():
            self.assertEqual({(p['pt'],p['role']) for p in d['products']},{(p['pt'],p['role']) for p in self.originals[k]['products']})
            self.assertNotIn('accessories',d)
            for c in d['combination_master']:self.assertFalse({'accessories','accessory_pt','panels','wifi'} & c.keys())
    def test_017_mono_context_count_1480(self):
        self.assertEqual(len(self.docs['monosplit']['pairs']),1480);self.assertEqual(len(self.docs['monosplit']['combination_master']),1480)
    def test_018_mono_pair_master_exact_consistency(self):self.assertEqual(self.configs['monosplit'],[])
    def test_019_mono_pair_contexts_unchanged(self):
        for a,b in zip(self.originals['monosplit']['pairs'],self.docs['monosplit']['pairs']):
            for key in ['scope','brand','family','variant','ui_pt','ue_pt','status','provenance','source','family_match_status']:
                self.assertEqual(a.get(key),b.get(key))
    def test_020_capacity_policy_unchanged(self):
        for k,d in self.docs.items():self.assertEqual(d['capacity_policy'],self.originals[k]['capacity_policy'])
    def test_021_contextual_capacity_values_unchanged(self):
        for k,d in self.docs.items():
            rows=d.get('pairs',d.get('ui_catalog'));before=self.originals[k].get('pairs',self.originals[k].get('ui_catalog'))
            for a,b in zip(before,rows):
                ca=a.get('ui_capacity',a);cb=b.get('ui_capacity',b)
                for f in ['commercial_btu','commercial_btu_source','cooling_kw','btu_from_kw_raw','btu_match','btu_match_source','btu_match_confidence','btu_match_delta_pct','btu_bucket_scope']:
                    self.assertEqual(ca.get(f),cb.get(f))
    def test_022_no_global_family_or_capacity_on_identity(self):
        for d in self.docs.values():
            for p in d['products']:self.assertFalse({'family','cooling_kw','btu_match','commercial_btu'} & p.keys())
    def test_023_normalization_typographic_positive_examples(self):
        for a,b in [('PUZ-M100YKA2-T','PUZ-M100YKA2 -T'),('AUW125U6RW8 T','AUW125U6RW8-T'),('AC100RXADNG/EU-T','AC100RXADNG/EU-t')]:
            self.assertEqual(P.normalized_model(a),P.normalized_model(b))
    def test_024_normalization_preserves_semantic_suffixes(self):
        for a,b in [('A','A8'),('A8','A9'),('V3','V4'),('VF','VFHZ'),('VG','VG2'),('VG2','VG3'),('E','E1')]:
            self.assertNotEqual(P.normalized_model('MODEL-'+a),P.normalized_model('MODEL-'+b))
    def test_025_letter_o_never_equals_zero(self):self.assertNotEqual(P.normalized_model('MXO25'),P.normalized_model('MX025'))
    def test_026_typography_duplicates_consolidated(self):
        d=self.docs['monosplit']
        for pt in ['50119141','50399031','99786656','99786663','99786687','99796419','50386345']:
            self.assertEqual(len(d['index_by_pt'][pt]),1)
    def test_027_physical_variant_boundaries_retained(self):
        for k,d in self.docs.items():
            for old_i,new_i in enumerate(self.recipe['migrations'][k]['old_to_new']):
                self.assertEqual(P.invariant_key(self.originals[k]['products'][old_i]),P.invariant_key(d['products'][new_i]))
    def test_028_documentary_models_not_lost(self):
        for k,d in self.docs.items():
            for old_i,new_i in enumerate(self.recipe['migrations'][k]['old_to_new']):
                a=self.originals[k]['products'][old_i];b=d['products'][new_i]
                self.assertTrue({a['model'],*a.get('model_aliases',[])} <= {b['model'],*b.get('model_aliases',[]),*b.get('documentary_models',[])})
    def test_029_same_normalized_model_never_merges_different_pt(self):
        for k,d in self.docs.items():
            for old_i,new_i in enumerate(self.recipe['migrations'][k]['old_to_new']):self.assertEqual(self.originals[k]['products'][old_i]['pt'],d['products'][new_i]['pt'])
    def test_030_catalog_labels_cannot_be_exact_manufacturer_models(self):
        for d in self.docs.values():
            for p in d['products']:
                if P.is_catalog_label(p['model']):
                    self.assertEqual(p.get('model_kind'),'CATALOG_LABEL');self.assertFalse(p.get('exact_manufacturer_model_eligible',True));self.assertIsNone(p.get('manufacturer_model'))
    def test_031_kosami_context_labels_not_separate_outdoor_products(self):
        d=self.docs['monosplit']
        for pt in ['50453610','50453627','50453634']:
            self.assertEqual(len(d['index_by_pt'][pt]),1)
            p=d['products'][d['index_by_pt'][pt][0]];self.assertGreaterEqual(len(p['catalog_labels']),3)
    def test_032_all_indices_reconstructed_independently(self):
        for d in self.docs.values():
            idx=independent_indices(d)
            self.assertEqual({k for k in d if P.is_index(k)},set(idx))
            for k,v in idx.items():self.assertEqual(d[k],v,k)
    def test_033_monosplit_configuration_key_index_preserves_context_duplicates(self):
        d=self.docs['monosplit'];self.assertEqual(len(d['index_by_configuration_key']),1477)
        self.assertEqual(sum(map(len,d['index_by_configuration_key'].values())),1480)
        self.assertTrue(all(isinstance(x,list) for x in d['index_by_configuration_key'].values()))
    def test_034_multisplit_configuration_keys_unique(self):
        d=self.docs['multisplit'];keys=[c['configuration_key'] for c in d['combination_master']]
        self.assertEqual(len(keys),len(set(keys)));self.assertEqual(len(keys),13127)
    def test_035_multisplit_master_all_authorized(self):self.assertEqual(self.configs['multisplit'],[])
    def test_036_explicit_combinations_preserved_exactly(self):
        a=self.originals['multisplit'];b=self.docs['multisplit']
        self.assertEqual([s['explicit_combinations'] for s in a['systems']],[s['explicit_combinations'] for s in b['systems']])
        self.assertEqual(sum(len(s['explicit_combinations']) for s in b['systems']),123)
    def test_037_all_explicit_combinations_in_master(self):
        d=self.docs['multisplit'];keys=d['index_by_configuration_key']
        for s in d['systems']:
            for ui in s['explicit_combinations']:self.assertIn(config_key(s['scope'],s['ue_pt'],ui),keys)
    def test_038_all_confirmed_rule_multisets_materialized(self):
        d=self.docs['multisplit'];seen=0
        for si,s in enumerate(d['systems']):
            for r in s['configuration_rules']:
                if r['status']=='CONFIRMED':
                    expected=expand_rule(r)
                    actual={tuple(c['ui_pts']) for c in d['combination_master'] if c['system_id']==si and c.get('rule_id')==r['id']}
                    self.assertEqual(actual,expected);seen+=len(expected)
        self.assertEqual(seen,13004)
    def test_039_no_unconfirmed_rule_authorizes(self):
        d=self.docs['multisplit']
        for c in d['combination_master']:
            if 'rule_id' in c:self.assertEqual(next(r for r in d['systems'][c['system_id']]['configuration_rules'] if r['id']==c['rule_id'])['status'],'CONFIRMED')
    def test_040_pairwise_only_has_zero_full_configurations(self):
        d=self.docs['multisplit'];used={c['system_id'] for c in d['combination_master']}
        for i,s in enumerate(d['systems']):
            if s['evidence'] in ['PAIRWISE_ONLY','NOT_CONFIRMED']:self.assertNotIn(i,used)
    def test_041_allowed_ui_unchanged(self):
        self.assertEqual([s['allowed_ui'] for s in self.docs['multisplit']['systems']],[s['allowed_ui'] for s in self.originals['multisplit']['systems']])
    def test_042_all_rules_unchanged(self):
        self.assertEqual([s['configuration_rules'] for s in self.docs['multisplit']['systems']],[s['configuration_rules'] for s in self.originals['multisplit']['systems']])
    def test_043_no_new_or_lost_combinations(self):
        for k,d in self.docs.items():
            a=self.originals[k]
            fields=['scope','ui_pt','ue_pt','ui_pts','ui_count','configuration_key','family','ui_btu_match','capacity_signature','capacity_signature_source','status','provenance','system_id','pair_id','rule_id']
            project=lambda x:[{f:r[f] for f in fields if f in r} for r in x['combination_master']]
            self.assertEqual(project(d),project(a))
    def test_044_duplicate_quantities_preserved(self):
        d=self.docs['multisplit'];key='MULTISPLIT|50196142|99788605,99788605,99788636'
        c=d['combination_master'][d['index_by_configuration_key'][key]]
        self.assertEqual(Counter(c['ui_pts']),Counter({'99788605':2,'99788636':1}));self.assertEqual(c['ui_count'],3)
    def test_045_no_xn_components(self):
        for d in self.docs.values():
            for c in d['combination_master']:
                for pt in c.get('ui_pts',[c.get('ui_pt')])+[c['ue_pt']]:self.assertNotRegex(pt,r'[xX*+]')
    def test_046_nonresidential_scopes_have_no_unproved_boms(self):
        d=self.docs['multisplit']
        self.assertFalse([c for c in d['combination_master'] if c['scope']!='MULTISPLIT'])
        self.assertEqual(Counter(s['scope'] for s in d['systems']),Counter({'MULTISPLIT':174,'SIMULTANEO':17,'MULTI_DHW':3,'VRF_BRANCH_SYSTEM':6}))
    def test_047_unresolved_statuses_and_original_fields_unchanged(self):
        for k,d in self.docs.items():
            self.assertEqual(len(d['unresolved_cases']),len(self.originals[k]['unresolved_cases']))
            for a,b in zip(self.originals[k]['unresolved_cases'],d['unresolved_cases']):
                self.assertEqual(a,{f:b[f] for f in a})
                self.assertIn(b['impact_category'],['PROPERTY_ONLY','IDENTITY','PAIRWISE_RELATION','FULL_CONFIGURATION','SOURCE_CONFLICT','NON_RESIDENTIAL_RULE','OTHER'])
    def test_048_unresolved_missing_edges_remain_missing(self):
        d=self.docs['multisplit']
        for c in d['unresolved_cases']:
            if c['code'] in ['NO_CONFIRMED_UI_RELATION','FULL_CONFIGURATION_EVIDENCE_MISSING']:
                for si,s in enumerate(d['systems']):
                    if s['ue_pt'] in c['pt'] and s['scope']==c.get('scope'):
                        if c['code']=='NO_CONFIRMED_UI_RELATION':self.assertFalse(s['allowed_ui'])
                        self.assertFalse([x for x in d['combination_master'] if x['system_id']==si])
    def test_049_resolved_cases_not_lost(self):
        for k,d in self.docs.items():self.assertEqual(d['resolved_cases'],self.originals[k]['resolved_cases'])
    def test_050_manual_registry_hash_and_version(self):
        h=P.file_sha(ROOT/'Knowledge/manual_overrides_clima.json')
        for d in self.docs.values():
            s=d['sources'][P.MANUAL_ID];self.assertEqual(s['sha256'],h);self.assertEqual(s['version'],'1.0.0');self.assertEqual(s['kind'],'USER_CONFIRMED')
    def test_051_manual_overrides_exactly_those_in_inputs(self):
        regenerated,_=P.extract_overrides(self.originals,self.recipe['build_spec']['inputs'])
        self.assertEqual(regenerated,self.manual);self.assertEqual(len(self.manual['overrides']),8)
    def test_052_manual_assertions_have_stable_backreferences(self):
        for o in self.manual['overrides']:
            self.assertEqual(o['status'],'CONFIRMED');self.assertEqual(o['original_provenance'],'USER_CONFIRMED');self.assertTrue(o['input_references'])
            for ref in o['input_references']:
                self.assertEqual(ref['source_sha256'],self.recipe['build_spec']['inputs'][ref['dataset']]['sha256'])
                self.assertIsNotNone(P.get_pointer(self.originals[ref['dataset']],ref['json_pointer']))
    def test_053_no_conversation_file_dependency_in_operational_registry(self):
        for d in self.docs.values():
            text=json.dumps(d['sources']).lower();self.assertNotIn('pasted text',text);self.assertNotIn('conversaz',text)
            for sid in ['USER_Q','USER_D']:self.assertEqual(d['sources'][sid]['alias_of'],P.MANUAL_ID)
    def test_054_all_source_references_resolve(self):
        keys={'source','explicit_combinations_source','ui_pool_source','system_capacity_source','commercial_btu_evidence'}
        for d in self.docs.values():
            registry=d['sources']
            for path,node in P.walk(d):
                if not isinstance(node,dict) or path.startswith('/sources'):continue
                for k,v in node.items():
                    if k in keys:
                        if isinstance(v,dict) and 'id' in v:self.assertIn(v['id'],registry,path)
                        elif isinstance(v,str):self.assertIn(v,registry,path)
                    if k in ('type_source','identity_confirmation') and isinstance(v,str):self.assertIn(v,registry,path)
                    if k.endswith('override_id') or k=='override_id':self.assertIn(v,self.manual['index_by_id'],path)
    def test_055_manufacturer_sources_preserved_without_inference(self):
        for k,d in self.docs.items():
            for sid,s in self.originals[k]['sources'].items():
                if s['kind']=='MANUFACTURER_CONFIRMED':
                    for f in ['kind','url','page','purpose']:self.assertEqual(d['sources'][sid].get(f),s.get(f))
                    self.assertIn(d['sources'][sid]['freeze_status'],['LOCAL_SHA256_VERIFIED','EXTERNAL_SOURCE_NOT_LOCALLY_FROZEN'])
    def test_056_available_source_hashes_match_declarations(self):
        for s in self.recipe['build_spec']['source_freezes'].values():self.assertTrue(s.get('declared_hash_matches',True))
    def test_057_manual_composition_never_becomes_pdf_confirmed(self):
        d=self.docs['multisplit'];key='MULTISPLIT|50196142|99788605,99788605,99788636'
        c=d['combination_master'][d['index_by_configuration_key'][key]]
        self.assertEqual(c['provenance'],'USER_CONFIRMED');self.assertEqual(c['source']['id'],P.MANUAL_ID)
    def test_058_haori_regression(self):
        rows=[p for p in self.docs['monosplit']['pairs'] if p['ui_pt']=='50383573' and p['ue_pt']=='50213924']
        self.assertTrue(rows);self.assertTrue(all(p['ui_capacity']['btu_match']==9000 for p in rows))
        self.assertFalse([p for p in self.docs['monosplit']['pairs'] if p['ui_pt']=='50383573' and p['ue_pt']=='50292301'])
    def test_059_panasonic_standard_regression(self):
        rows=[p for p in self.docs['monosplit']['pairs'] if p['ui_pt']=='50117260' and 'STANDARD' in p['family']]
        self.assertTrue(rows);self.assertEqual({p['ue_pt'] for p in rows},{'50003952'})
        self.assertTrue(all(p['ui_capacity']['btu_match']==21000 for p in rows))
    def test_060_mitsubishi_white_not_ruby(self):
        d=self.docs['multisplit'];key='MULTISPLIT|50196142|99788605,99788605,99788636'
        c=d['combination_master'][d['index_by_configuration_key'][key]]
        self.assertNotIn('99788599',c['ui_pts'])
        for pt in set(c['ui_pts']):self.assertTrue(all(d['products'][i]['color_base']=='WHITE' for i in d['index_by_pt'][pt]))
    def test_061_daikin_ffa_role_revision(self):
        for d in self.docs.values():
            for i in d['index_by_pt']['99718206']:
                self.assertEqual(d['products'][i]['role'],'UI');self.assertEqual(d['products'][i]['model'],'FFA25A9')
    def test_062_daikin_rxm25_multiple_contexts_one_identity(self):
        d=self.docs['monosplit'];self.assertEqual(len(d['index_by_pt']['50308071']),1)
        families={p['family'] for p in d['pairs'] if p['ue_pt']=='50308071'};self.assertGreater(len(families),1)
    def test_063_venus_scope_guard(self):
        for d in self.docs.values():
            e=d['pt_equivalences'][0];self.assertFalse(e['inherit_pairing']);self.assertEqual(e['pt_by_scope'],{'MONOSPLIT':['50282814'],'MULTISPLIT':['50282883']})
        for c in self.docs['multisplit']['combination_master']:self.assertNotEqual(c['ue_pt'],'50282814')
        for c in self.docs['monosplit']['combination_master']:self.assertNotEqual(c['ue_pt'],'50282883')
    def test_064_paros_identity_and_noninheritance(self):
        d=self.docs['monosplit']
        expected={'50453016':('UI','WHITE'),'50453054':('UI','BLACK'),'50452965':('UE',None)}
        for pt,(role,color) in expected.items():
            for i in d['index_by_pt'][pt]:
                p=d['products'][i];self.assertEqual(p['role'],role);self.assertEqual(p['color_base'],color)
        for c in self.docs['multisplit']['combination_master']:self.assertFalse({'50453054','50453061'} & set(c['ui_pts']))
    def test_065_haier_flexis_color_separation(self):
        for d in self.docs.values():
            for pt,color in [('50026470','WHITE'),('50021635','BLACK')]:
                for i in d['index_by_pt'].get(pt,[]):self.assertEqual(d['products'][i]['color_base'],color)
    def test_066_bosch_series_is_not_btu(self):
        d=self.docs['monosplit']
        a=[p for p in d['pairs'] if p['ui_pt']=='50276394'];b=[p for p in d['pairs'] if p['ui_pt']=='50276523']
        self.assertTrue(a and b)
        self.assertTrue(all(p['ui_capacity']['btu_match']==7000 for p in a))
        self.assertTrue(all(p['ui_capacity']['btu_match']==18000 for p in b))
        self.assertTrue(all(p['ui_capacity']['commercial_btu'] is None for p in a+b))
    def test_067_haier_no_system_kw_on_individual_ui(self):
        for c in self.docs['multisplit']['ui_catalog']:
            if c['pt']=='50284115':self.assertNotEqual(c['cooling_kw'],4.8)
        self.assertEqual(next(s for s in self.docs['multisplit']['systems'] if s['ue_pt']=='50131365')['system_cooling_kw'],4.8)
    def test_068_panasonic_same_pt_contextual_capacities(self):
        rows=[p for p in self.docs['monosplit']['pairs'] if p['ui_pt']=='50003709']
        self.assertGreater(len({p['ui_capacity']['cooling_kw'] for p in rows}),1)
    def test_069_typographic_canonicalization_does_not_change_revision(self):
        for k,d in self.docs.items():
            for g in self.recipe['migrations'][k]['consolidated']:
                before=[self.originals[k]['products'][i] for i in g['old_product_ids']]
                p=d['products'][g['new_product_id']]
                for q in before:
                    self.assertTrue(P.normalized_model(q['model'])==P.normalized_model(p['model']) or q['model'] in p.get('model_aliases',[]))
    def test_070_residential_and_dhw_same_pt_scopes_not_merged(self):
        d=self.docs['multisplit']
        before={(p['pt'],p['scope'],p['role']) for p in self.originals['multisplit']['products']}
        after={(p['pt'],p['scope'],p['role']) for p in d['products']};self.assertEqual(before,after)
    def test_071_quantity_corruption_is_detected(self):
        d=copy.deepcopy(self.docs['multisplit']);d['combination_master'][1]['ui_pts'].pop()
        self.assertTrue(inspect_configurations('multisplit',d))
    def test_072_role_corruption_is_detected(self):
        d=copy.deepcopy(self.docs['monosplit']);d['products'][d['pairs'][0]['ui_product_id']]['role']='UE'
        self.assertTrue(any(x['code']=='ROLE_MISMATCH' for x in inspect_references('monosplit',d)))
    def test_073_scope_corruption_is_detected(self):
        d=copy.deepcopy(self.docs['multisplit']);i=d['systems'][0]['ue_product_id'];d['products'][i]['scope']='MONOSPLIT'
        self.assertTrue(any(x['code']=='SCOPE_LEAK' for x in inspect_references('multisplit',d)))
    def test_074_unauthorized_rule_status_is_detected(self):
        d=copy.deepcopy(self.docs['multisplit'])
        next(r for s in d['systems'] for r in s['configuration_rules'] if r['status']=='CONFIRMED')['status']='NOT_CONFIRMED'
        self.assertTrue(any(x['code']=='UNAUTHORIZED_RULE' for x in inspect_configurations('multisplit',d)))
    def test_075_identity_alias_registry_contains_only_source_spellings(self):
        for k,d in self.docs.items():
            for ni,p in enumerate(d['products']):
                source_spellings={x for oi,nj in enumerate(self.recipe['migrations'][k]['old_to_new']) if ni==nj
                                  for x in [self.originals[k]['products'][oi]['model']]+self.originals[k]['products'][oi].get('model_aliases',[])}
                self.assertTrue(set(p.get('model_aliases',[]))<=source_spellings)
    def test_076_no_timestamp_in_operational_datasets(self):
        for d in self.docs.values():self.assertFalse({'generated_at','timestamp','build_timestamp_utc'} & d.keys())
    def test_077_deterministic_build_two_independent_processes(self):
        with tempfile.TemporaryDirectory(prefix='clima-production-test-') as tmp:
            base=Path(tmp);spec=base/'spec.json';spec.write_text(json.dumps(self.recipe['build_spec'],ensure_ascii=False))
            for k,o in self.originals.items():(base/P.SOURCE_NAME[k]).write_bytes(P.serialize(o))
            hashes=[]
            for run,seed in [('first','117'),('second','9081')]:
                cmd=[sys.executable,str(TOOLS),'--mono',str(base/P.SOURCE_NAME['monosplit']),
                     '--multi',str(base/P.SOURCE_NAME['multisplit']),'--spec',str(spec),'--out',str(base/run)]
                env=dict(os.environ,PYTHONHASHSEED=seed)
                cp=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=90)
                self.assertEqual(cp.returncode,0,cp.stderr)
                h={name:P.file_sha(base/run/'Knowledge'/name) for name in [*P.OUTPUT_NAME.values(),'manual_overrides_clima.json']}
                hashes.append(h)
            self.assertEqual(hashes[0],hashes[1])
            actual={name:P.file_sha(ROOT/'Knowledge'/name) for name in hashes[0]};self.assertEqual(actual,hashes[0])
            type(self).determinism_result={'processes':2,'different_pythonhashseed':[117,9081],
                'byte_identical':True,'first':hashes[0],'second':hashes[1],'matches_delivered_files':True,
                'source_input_bytes_reconstructed_and_sha256_verified':True}
    def test_078_generator_sha_matches_release_spec(self):self.assertEqual(P.file_sha(TOOLS),self.recipe['build_spec']['generator_sha256'])
    def test_079_final_manifest_hashes_match(self):
        path=ROOT/'Knowledge/clima_master_manifest.json'
        if CERTIFY:return
        manifest=load(path)
        for key,record in manifest['files'].items():
            f=ROOT/record['filename'];self.assertEqual(P.file_sha(f),record['sha256'],key)
            if 'size_bytes' in record:self.assertEqual(f.stat().st_size,record['size_bytes'])
        self.assertEqual(manifest['release_status'],'PRODUCTION_APPROVED')


class CollectResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'test':test._testMethodName,'passed':True})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'test':test._testMethodName,'passed':False,'detail':self._exc_info_to_string(err,test)})
    def addError(self,test,err):super().addError(test,err);self.records.append({'test':getattr(test,'_testMethodName',str(test)),'passed':False,'detail':self._exc_info_to_string(err,test)})


def summary(kind,d,original,migration):
    cases=Counter(x['impact_category'] for x in d['unresolved_cases'])
    s={'products_input':len(original['products']),'products':len(d['products']),
       'distinct_pt':len(pt_set(d)),'duplicate_identities_consolidated':migration['duplicates_consolidated'],
       'consolidation_groups':len(migration['consolidated']),
       'catalog_label_products':sum(p.get('model_kind')=='CATALOG_LABEL' for p in d['products']),
       'combination_master':len(d['combination_master']),'unresolved_total':len(d['unresolved_cases']),
       'unresolved_by_impact':dict(sorted(cases.items()))}
    if kind=='monosplit':s.update({'pairs':len(d['pairs']),'unique_configuration_keys':len(d['index_by_configuration_key']),'other_systems':len(d['other_systems'])})
    else:s.update({'systems':len(d['systems']),'systems_by_scope':dict(Counter(x['scope'] for x in d['systems'])),
        'allowed_ui':sum(len(x['allowed_ui']) for x in d['systems']),
        'explicit_combinations':sum(len(x['explicit_combinations']) for x in d['systems']),
        'combinations_generated_by_confirmed_rules':sum('rule_id' in c for c in d['combination_master']),
        'confirmed_rules':sum(r['status']=='CONFIRMED' for s in d['systems'] for r in s['configuration_rules']),
        'non_confirmed_rules':sum(r['status']!='CONFIRMED' for s in d['systems'] for r in s['configuration_rules']),
        'pairwise_only_systems':sum(s['evidence']=='PAIRWISE_ONLY' for s in d['systems'])})
    return s


def certify(result):
    cls=ProductionTests;docs=cls.docs;originals=cls.originals;recipe=cls.recipe
    failed=len(result.failures)+len(result.errors);approved=failed==0
    status='PRODUCTION_APPROVED' if approved else 'PRODUCTION_BLOCKED'
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    issues=[i for es in [*cls.refs.values(),*cls.configs.values()] for i in es]
    merged_cases={}
    for k,d in docs.items():
        for c in d['unresolved_cases']:
            key=c['id']
            if key not in merged_cases:merged_cases[key]={f:copy.deepcopy(v) for f,v in c.items()}
            merged_cases[key].setdefault('datasets',[]).append(k)
    external=[{'source_id':sid,'code':'EXTERNAL_SOURCE_NOT_LOCALLY_FROZEN','production_blocking':False,
               'url':s['url'],'page':s.get('page'),'purpose':s.get('purpose'),
               'verification_status':s['verification_status']}
              for sid,s in docs['multisplit']['sources'].items() if s.get('freeze_status')=='EXTERNAL_SOURCE_NOT_LOCALLY_FROZEN']
    summaries={k:summary(k,d,originals[k],recipe['migrations'][k]) for k,d in docs.items()}
    before=set.union(*(pt_set(d) for d in originals.values()));after=set.union(*(pt_set(d) for d in docs.values()))
    file_info={k:{'filename':'Knowledge/'+P.OUTPUT_NAME[k],'sha256':P.file_sha(ROOT/'Knowledge'/P.OUTPUT_NAME[k]),
                    'size_bytes':(ROOT/'Knowledge'/P.OUTPUT_NAME[k]).stat().st_size,
                    'products':len(d['products']),'combinations':len(d['combination_master']),
                    **({'pairs':len(d['pairs'])} if k=='monosplit' else {'systems':len(d['systems'])})} for k,d in docs.items()}
    file_info['manual_overrides']={'filename':'Knowledge/manual_overrides_clima.json',
        'sha256':P.file_sha(ROOT/'Knowledge/manual_overrides_clima.json'),
        'size_bytes':(ROOT/'Knowledge/manual_overrides_clima.json').stat().st_size,'overrides':len(cls.manual['overrides'])}
    blockers=[r for r in result.records if not r['passed']]
    audit={'schema_version':'1.0.0','dataset_schema_version':'3.0.0','dataset_version':P.DATASET_VERSION,
        'release_status':status,'build_timestamp_utc':now,'production_policy':'FAIL_CLOSED',
        'source_selection':{'actual_files':recipe['build_spec']['inputs'],
           'requested_download_names':['clima_monosplit_light (2)(1).json','clima_multisplit_light (2)(1).json'],
           'note':'Requested download-copy names were not present; used the two existing schema-3.0.0 master attachments identified by the recorded exact hashes. No older version substituted.'},
        'build_spec':recipe['build_spec'],'monosplit':summaries['monosplit'],'multisplit':summaries['multisplit'],
        'global':{'distinct_principal_pt_union':len(after),'pt_lost':sorted(before-after),'pt_invented':sorted(after-before),
           'invalid_references':sum(i['code'] in ('INVALID_REFERENCE','REFERENCE_PT_MISMATCH','INVALID_RULE_PT') for i in issues),
           'role_mismatches':sum(i['code']=='ROLE_MISMATCH' for i in issues),'scope_leaks':sum(i['code']=='SCOPE_LEAK' for i in issues),
           'unauthorized_combinations':sum(i['code'].startswith('UNAUTHORIZED') for i in issues),
           'index_errors':sum(d[k]!=v for d in docs.values() for k,v in independent_indices(d).items()),
           'source_errors':sum(not r['passed'] for r in result.records if any(x in r['test'] for x in ['source_','manual_'])),
           'manual_overrides_migrated':len(cls.manual['overrides']),
           'regressions_passed':sum(r['passed'] and 58<=int(r['test'].split('_')[1])<=70 for r in result.records),
           'tests_passed':sum(r['passed'] for r in result.records),'tests_failed':failed,
           'deterministic_build':bool(cls.determinism_result and cls.determinism_result['byte_identical']),
           'unresolved_unique':len(merged_cases),'duplicate_identities_consolidated':sum(s['duplicate_identities_consolidated'] for s in summaries.values())},
        'tests':result.records,'hard_blockers':blockers,'structural_issues':issues,
        'source_warnings':external,'unresolved_counts_by_category':dict(Counter(c['impact_category'] for c in merged_cases.values())),
        'unresolved_cases':list(merged_cases.values()),
        'unresolved_production_blocking_policy':'Existing unconfirmed cases do not block release when confined to their original property/edge/scope. They remain non-authorizing. Any structural leakage is a hard release failure.',
        'manual_migration_note':'Only the 8 explicit USER_Q/USER_D assertions carried by the two v3 datasets were migrated. Other documentary aliases were preserved without fabricating missing D01-D07 confirmation records. commercial_btu_source USER_Q is retained as a backward-compatible provenance category, resolved to the frozen registry.',
        'source_freezing_note':'PDF and V2 hashes verified only as already referenced local sources; no re-extraction or web access. Manufacturer URLs not locally available retain inherited verification status and are explicit nonblocking freeze warnings.',
        'schema_migration':{'from':'3.0.0','to':'3.0.0','logical_schema_changed':False,
           'changes':['Add release metadata','Remap product offsets after same-PT typographic/explicit-alias consolidation',
                      'Preserve original models in documentary_models/model_aliases and pair contexts',
                      'Mark generic catalogue labels as not eligible for exact manufacturer-model evidence',
                      'Add stable manual evidence registry and unresolved impact annotations','Rebuild all existing indices'],
           'backward_compatibility':'Array/record/ref shapes retained. Per-file legacy_product_id_map tied to exact input hash; reversible audit recovers the original input bytes. No family/capacity moved into physical identity.'},
        'migrations':recipe['migrations'],'determinism':cls.determinism_result,
        'output_files':file_info,'runtime_integrated':False,'accessory_master_modified':False,
        'audit_scope':'Production hardening of input v3 assertions, not a fresh catalogue/manufacturer validation.'}
    # Status is decided from actual executed hard tests, not from a desired release label.
    if not approved:
        for k,d in docs.items():
            d['release_status']='PRODUCTION_BLOCKED'
            (ROOT/'Knowledge'/P.OUTPUT_NAME[k]).write_bytes(P.serialize(d))
            file_info[k]['sha256']=P.file_sha(ROOT/'Knowledge'/P.OUTPUT_NAME[k]);file_info[k]['size_bytes']=(ROOT/'Knowledge'/P.OUTPUT_NAME[k]).stat().st_size
    report=ROOT/'reports/clima_master_production_audit.json';report.write_bytes(P.serialize(audit))
    files=copy.deepcopy(file_info)
    files['audit']={'filename':'reports/clima_master_production_audit.json','sha256':P.file_sha(report),'size_bytes':report.stat().st_size}
    files['tests']={'filename':'tests/test_clima_master_production.py','sha256':P.file_sha(Path(__file__)),'size_bytes':Path(__file__).stat().st_size}
    files['generator']={'filename':'tools/promote_clima_master.py','sha256':P.file_sha(TOOLS),'size_bytes':TOOLS.stat().st_size}
    manifest={'release_status':status,'dataset_version':P.DATASET_VERSION,'schema_version':'3.0.0',
        'files':files,'fail_closed':True,'build_timestamp_utc':now,'source_hashes':recipe['build_spec']['inputs'],
        'generator_version':P.GENERATOR_VERSION,'generator_git_commit':None,
        'generator_sha256':P.file_sha(TOOLS),
        'regression_suite_result':{'tests_passed':audit['global']['tests_passed'],'tests_failed':failed,
            'scope':'79 production checks; original-v3 byte reconstruction; independent exact-pool expansion; named regressions; two isolated builds'},
        'unresolved_counts_by_category':audit['unresolved_counts_by_category'],
        'external_sources_not_locally_frozen':[s['source_id'] for s in external],
        'runtime_integration_status':'NOT_PERFORMED','approved_scope':'OFFLINE_DATA_RELEASE_ONLY_NOT_INSTALLATION_OR_RUNTIME_DEPLOYMENT',
        'hard_blockers':[r['test'] for r in blockers]}
    (ROOT/'Knowledge/clima_master_manifest.json').write_bytes(P.serialize(manifest))
    seed=ROOT/'reports/promotion_build_seed.json'
    if seed.exists():seed.unlink()
    print(json.dumps({'release_status':status,**summaries,'global':audit['global'],
          'sha256':{k:v['sha256'] for k,v in files.items()}},indent=2,ensure_ascii=False))


def main():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ProductionTests)
    runner=unittest.TextTestRunner(verbosity=2,resultclass=CollectResult)
    result=runner.run(suite)
    if CERTIFY:certify(result)
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
