import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/Principale/Documents/ChatGPT/vector_db_pt";
const reportDir = path.join(root, "reports", "clima_ab");
const outputPath = path.join(reportDir, "before_after.xlsx");
const font = "Arial";

const readJson = async (name) => JSON.parse(await fs.readFile(path.join(reportDir, name), "utf8"));
const readJsonl = async (name) => (await fs.readFile(path.join(reportDir, name), "utf8"))
  .split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
const text = (value) => value == null ? "" : typeof value === "string" ? value : JSON.stringify(value);
const yesNo = (value) => value ? "TRUE" : "FALSE";

const after = await readJson("after_summary.json");
const summary = await readJson("before_after_summary.json");
const diffs = await readJsonl("before_after_diff.jsonl");

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("Summary");
const allSheet = workbook.worksheets.add("All rows");
const suspiciousSheet = workbook.worksheets.add("Top 50 suspicious");
const regressionSheet = workbook.worksheets.add("Regression");

function styleTitle(sheet, range) {
  range.format.font = { name: font, size: 16, bold: true, color: "#172554" };
  range.format.rowHeight = 34;
  sheet.showGridLines = false;
}

function styleHeader(range) {
  range.format = {
    fill: "#1E3A5F",
    font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };
  range.format.rowHeight = 30;
}

function styleBody(range) {
  range.format.font = { name: font, size: 10, color: "#1F2937" };
  range.format.verticalAlignment = "top";
}

summarySheet.getRange("A1").values = [["CLIMA runtime BEFORE / AFTER"]];
styleTitle(summarySheet, summarySheet.getRange("A1:C1"));
summarySheet.getRange("A2").values = [["Dataset PT26_CLIMA_PROD_1 · 4,453 righe CLIMA · baseline congelata"]];
summarySheet.getRange("A2:C2").format.font = { name: font, size: 10, italic: true, color: "#4B5563" };

const beforeIndicators = summary.before_indicators;
const afterIndicators = summary.after_indicators;
const metricRows = [
  ["Indicatore", "BEFORE", "AFTER", "Delta"],
  ["Righe", beforeIndicators.rows, afterIndicators.rows, afterIndicators.rows - beforeIndicators.rows],
  ["Automatic MPN", beforeIndicators.automatic_mpn, afterIndicators.automatic_mpn, afterIndicators.automatic_mpn - beforeIndicators.automatic_mpn],
  ["Errori runtime", beforeIndicators.failed, afterIndicators.failed, afterIndicators.failed - beforeIndicators.failed],
  ["DISCOVERY_ONLY", beforeIndicators.main_unit_status_counts.DISCOVERY_ONLY || 0, afterIndicators.main_unit_status_counts.DISCOVERY_ONLY || 0, (afterIndicators.main_unit_status_counts.DISCOVERY_ONLY || 0) - (beforeIndicators.main_unit_status_counts.DISCOVERY_ONLY || 0)],
  ["EXACT", beforeIndicators.main_unit_status_counts.EXACT || 0, afterIndicators.main_unit_status_counts.EXACT || 0, (afterIndicators.main_unit_status_counts.EXACT || 0) - (beforeIndicators.main_unit_status_counts.EXACT || 0)],
  ["REVISION_CANDIDATE", beforeIndicators.main_unit_status_counts.REVISION_CANDIDATE || 0, afterIndicators.main_unit_status_counts.REVISION_CANDIDATE || 0, (afterIndicators.main_unit_status_counts.REVISION_CANDIDATE || 0) - (beforeIndicators.main_unit_status_counts.REVISION_CANDIDATE || 0)],
  ["AMBIGUOUS_REVISION", beforeIndicators.main_unit_status_counts.AMBIGUOUS_REVISION || 0, afterIndicators.main_unit_status_counts.AMBIGUOUS_REVISION || 0, (afterIndicators.main_unit_status_counts.AMBIGUOUS_REVISION || 0) - (beforeIndicators.main_unit_status_counts.AMBIGUOUS_REVISION || 0)],
  ["NO_MAIN_UNIT_SELECTED", beforeIndicators.main_unit_status_counts.NO_MAIN_UNIT_SELECTED || 0, afterIndicators.main_unit_status_counts.NO_MAIN_UNIT_SELECTED || 0, (afterIndicators.main_unit_status_counts.NO_MAIN_UNIT_SELECTED || 0) - (beforeIndicators.main_unit_status_counts.NO_MAIN_UNIT_SELECTED || 0)],
  ["VERIFIED_FULL_COMBINATION", beforeIndicators.configuration_status_counts.VERIFIED_FULL_COMBINATION || 0, afterIndicators.configuration_status_counts.VERIFIED_FULL_COMBINATION || 0, (afterIndicators.configuration_status_counts.VERIFIED_FULL_COMBINATION || 0) - (beforeIndicators.configuration_status_counts.VERIFIED_FULL_COMBINATION || 0)],
  ["VERIFIED_MASTER_PAIR", beforeIndicators.configuration_status_counts.VERIFIED_MASTER_PAIR || 0, afterIndicators.configuration_status_counts.VERIFIED_MASTER_PAIR || 0, (afterIndicators.configuration_status_counts.VERIFIED_MASTER_PAIR || 0) - (beforeIndicators.configuration_status_counts.VERIFIED_MASTER_PAIR || 0)],
  ["CONFIGURAZIONE_NON_CONFERMATA", beforeIndicators.configuration_status_counts.CONFIGURAZIONE_NON_CONFERMATA || 0, afterIndicators.configuration_status_counts.CONFIGURAZIONE_NON_CONFERMATA || 0, (afterIndicators.configuration_status_counts.CONFIGURAZIONE_NON_CONFERMATA || 0) - (beforeIndicators.configuration_status_counts.CONFIGURAZIONE_NON_CONFERMATA || 0)],
];
summarySheet.getRange(`A4:D${3 + metricRows.length}`).values = metricRows;
styleHeader(summarySheet.getRange("A4:D4"));
styleBody(summarySheet.getRange(`A5:D${3 + metricRows.length}`));
summarySheet.getRange(`B5:D${3 + metricRows.length}`).format.numberFormat = "#,##0";

const detailStart = 18;
const detailRows = [
  ["Metrica AFTER / DIFF", "Valore"],
  ["Configurazioni confermate", after.confirmed_configuration_count],
  ["MASTER_EXACT_PAIR", after.master_exact_pair_count],
  ["MASTER_EXACT_CONFIGURATION", after.master_exact_configuration_count],
  ["MASTER_EXACT_IDENTITY", after.master_exact_identity_count],
  ["Master exact totale", after.master_exact_total_count],
  ["Resolver master diretto", after.direct_master_resolver_count],
  ["Legacy fallback", after.legacy_fallback_count],
  ["Fallback validato dal master", after.legacy_fallback_master_validated_count],
  ["Master unresolved", after.master_unresolved_count],
  ["MPN final allowed TRUE", after.mpn_final_allowed_counts.true || 0],
  ["MPN final allowed FALSE", after.mpn_final_allowed_counts.false || 0],
  ["Righe CHANGED", summary.diff_classification_counts.CHANGED],
  ["Righe UNCHANGED", summary.diff_classification_counts.UNCHANGED],
  ["MPN cambiato", summary.rows_with_mpn_changed],
  ["Quantità UI cambiata", summary.rows_with_ui_quantity_changed],
  ["Colore cambiato", summary.rows_with_color_changed],
  ["Revisione/modello cambiato", summary.rows_with_revision_or_model_changed],
  ["Miglioramenti verificati", summary.verified_improvements],
  ["Regressioni verificate", summary.verified_regressions],
  ["Changed unverified", summary.changed_unverified],
  ["Accessori risolti", after.accessory_resolved_count],
  ["Accessori ambigui", after.accessory_ambiguous_count],
];
summarySheet.getRange(`A${detailStart}:B${detailStart + detailRows.length - 1}`).values = detailRows;
styleHeader(summarySheet.getRange(`A${detailStart}:B${detailStart}`));
styleBody(summarySheet.getRange(`A${detailStart + 1}:B${detailStart + detailRows.length - 1}`));
summarySheet.getRange(`B${detailStart + 1}:B${detailStart + detailRows.length - 1}`).format.numberFormat = "#,##0";

const perf = summary.performance_comparison;
const perfRows = [
  ["Performance", "BEFORE", "AFTER", "Delta"],
  ["Wall clock (s)", perf.before.wall_clock_seconds, perf.after.wall_clock_seconds, perf.delta.wall_clock_seconds],
  ["Runtime cumulativo (s)", perf.before.runtime_cumulative_seconds, perf.after.runtime_cumulative_seconds, perf.delta.runtime_cumulative_seconds],
  ["Mean (ms)", perf.before.runtime_mean_ms, perf.after.runtime_mean_ms, perf.delta.runtime_mean_ms],
  ["Median (ms)", perf.before.runtime_median_ms, perf.after.runtime_median_ms, perf.delta.runtime_median_ms],
  ["P95 (ms)", perf.before.runtime_p95_ms, perf.after.runtime_p95_ms, perf.delta.runtime_p95_ms],
  ["P99 (ms)", perf.before.runtime_p99_ms, perf.after.runtime_p99_ms, perf.delta.runtime_p99_ms],
];
summarySheet.getRange(`F4:I${3 + perfRows.length}`).values = perfRows;
styleHeader(summarySheet.getRange("F4:I4"));
styleBody(summarySheet.getRange(`F5:I${3 + perfRows.length}`));
summarySheet.getRange(`G5:I${3 + perfRows.length}`).format.numberFormat = "#,##0.000";

summarySheet.getRange("F13").values = [["Input e classificazione"]];
summarySheet.getRange("F13:I13").format.font = { name: font, size: 11, bold: true, color: "#172554" };
summarySheet.getRange("F14:I19").values = [
  ["Frozen input SHA256", after.input_assertions.frozen_sha256, "", ""],
  ["BEFORE SHA256", after.input_assertions.before_sha256, "", ""],
  ["Row ID in stessa sequenza", yesNo(after.input_assertions.row_id_sequence_equal), "", ""],
  ["Titoli identici", yesNo(after.input_assertions.titles_equal), "", ""],
  ["Reference/input identici", yesNo(after.input_assertions.original_reference_fields_equal), "", ""],
  ["Flag master runtime", yesNo(after.input_assertions.clima_master_runtime_enabled), "", ""],
];
styleBody(summarySheet.getRange("F14:I19"));

summarySheet.getRange("A4:D4").conditionalFormats.addCustom("=D5<0", { font: { color: "#B91C1C" } });
summarySheet.getRange("A1:I45").format.wrapText = true;
summarySheet.getRange("A:A").format.columnWidth = 34;
summarySheet.getRange("B:D").format.columnWidth = 15;
summarySheet.getRange("E:E").format.columnWidth = 3;
summarySheet.getRange("F:F").format.columnWidth = 26;
summarySheet.getRange("G:I").format.columnWidth = 18;

const headers = [
  "row_id", "title", "diff", "quality", "reason", "before_mpn", "after_mpn",
  "before_main_mpn", "after_main_mpn", "ui_pt_changed", "ue_pt_changed",
  "ui_quantity_changed", "revision_model_changed", "color_changed", "family_changed",
  "accessory_changed", "configuration_changed", "final_allowed_changed",
  "before_configuration", "after_configuration", "before_final_allowed", "after_final_allowed",
  "master_resolution_type", "legacy_fallback", "suspicion_score", "suspicion_reasons"
];
const diffRows = diffs.map((row) => [
  row.row_id, row.title, row.diff_classification, row.quality_classification, row.reason || "",
  row.before_mpn || "", row.after_mpn || "", row.before_main_unit_mpn || "", row.after_main_unit_mpn || "",
  yesNo(row.changes.ui_pt_changed), yesNo(row.changes.ue_pt_changed), yesNo(row.changes.ui_quantity_changed),
  yesNo(row.changes.revision_changed), yesNo(row.changes.color_changed), yesNo(row.changes.family_changed),
  yesNo(row.changes.accessory_pt_changed), yesNo(row.changes.configuration_status_changed),
  yesNo(row.changes.mpn_final_allowed_changed), row.before_configuration_status || "", row.after_configuration_status || "",
  yesNo(row.before_mpn_final_allowed), yesNo(row.after_mpn_final_allowed), row.master_resolution_type || "",
  yesNo(row.legacy_fallback_used), row.suspicion_score, (row.suspicion_reasons || []).join(", "),
]);
allSheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
allSheet.getRangeByIndexes(1, 0, diffRows.length, headers.length).values = diffRows;
styleHeader(allSheet.getRangeByIndexes(0, 0, 1, headers.length));
styleBody(allSheet.getRangeByIndexes(1, 0, diffRows.length, headers.length));
allSheet.freezePanes.freezeRows(1);
allSheet.freezePanes.freezeColumns(2);
allSheet.showGridLines = false;
allSheet.getRange("A:A").format.columnWidth = 16;
allSheet.getRange("B:B").format.columnWidth = 58;
allSheet.getRange("C:E").format.columnWidth = 22;
allSheet.getRange("F:I").format.columnWidth = 30;
allSheet.getRange("J:R").format.columnWidth = 14;
allSheet.getRange("S:X").format.columnWidth = 25;
allSheet.getRange("Y:Y").format.columnWidth = 14;
allSheet.getRange("Z:Z").format.columnWidth = 42;
allSheet.getRange(`B2:B${diffRows.length + 1}`).format.wrapText = true;
allSheet.getRange(`Z2:Z${diffRows.length + 1}`).format.wrapText = true;
allSheet.tables.add(`A1:Z${diffRows.length + 1}`, true, "ClimaBeforeAfterTable").style = "TableStyleMedium2";

const suspicious = summary.top_50_suspicious_changes;
const suspiciousHeaders = [
  "Rank", "row_id", "suspicion_score", "suspicion_reasons", "quality", "reason", "title",
  "before_main_mpn", "after_main_mpn", "before_configuration", "after_configuration",
  "legacy_fallback", "master_resolution_type"
];
const suspiciousRows = suspicious.map((row, index) => [
  index + 1, row.row_id, row.suspicion_score, (row.suspicion_reasons || []).join(", "),
  row.quality_classification, row.reason || "", row.title, row.before_main_unit_mpn || "",
  row.after_main_unit_mpn || "", row.before_configuration_status || "", row.after_configuration_status || "",
  yesNo(row.legacy_fallback_used), row.master_resolution_type || "",
]);
suspiciousSheet.getRangeByIndexes(0, 0, 1, suspiciousHeaders.length).values = [suspiciousHeaders];
suspiciousSheet.getRangeByIndexes(1, 0, suspiciousRows.length, suspiciousHeaders.length).values = suspiciousRows;
styleHeader(suspiciousSheet.getRangeByIndexes(0, 0, 1, suspiciousHeaders.length));
styleBody(suspiciousSheet.getRangeByIndexes(1, 0, suspiciousRows.length, suspiciousHeaders.length));
suspiciousSheet.freezePanes.freezeRows(1);
suspiciousSheet.showGridLines = false;
suspiciousSheet.getRange("A:C").format.columnWidth = 14;
suspiciousSheet.getRange("D:F").format.columnWidth = 24;
suspiciousSheet.getRange("G:G").format.columnWidth = 62;
suspiciousSheet.getRange("H:M").format.columnWidth = 28;
suspiciousSheet.getRange(`D2:M${suspiciousRows.length + 1}`).format.wrapText = true;
suspiciousSheet.tables.add(`A1:M${suspiciousRows.length + 1}`, true, "ClimaSuspiciousTable").style = "TableStyleMedium4";

const regressionHeaders = ["Caso", "Query", "Expected", "Actual", "Esito", "Configuration status", "MPN final allowed"];
const regressionRows = summary.named_regressions.map((row) => [
  row.name, row.query, row.expected.join(" + "), row.actual.join(" + "), row.passed ? "PASS" : "FAIL",
  row.configuration_status || "", yesNo(row.mpn_final_allowed),
]);
regressionSheet.getRangeByIndexes(0, 0, 1, regressionHeaders.length).values = [regressionHeaders];
regressionSheet.getRangeByIndexes(1, 0, regressionRows.length, regressionHeaders.length).values = regressionRows;
styleHeader(regressionSheet.getRangeByIndexes(0, 0, 1, regressionHeaders.length));
styleBody(regressionSheet.getRangeByIndexes(1, 0, regressionRows.length, regressionHeaders.length));
regressionSheet.freezePanes.freezeRows(1);
regressionSheet.showGridLines = false;
regressionSheet.getRange("A:A").format.columnWidth = 30;
regressionSheet.getRange("B:B").format.columnWidth = 48;
regressionSheet.getRange("C:D").format.columnWidth = 38;
regressionSheet.getRange("E:G").format.columnWidth = 24;
regressionSheet.getRange(`A2:G${regressionRows.length + 1}`).format.wrapText = true;
regressionSheet.tables.add(`A1:G${regressionRows.length + 1}`, true, "ClimaRegressionTable").style = "TableStyleMedium2";

const checks = {};
checks.summary = (await workbook.inspect({ kind: "table", range: "Summary!A1:I40", include: "values,formulas", tableMaxRows: 40, tableMaxCols: 10 })).ndjson;
checks.allRows = (await workbook.inspect({ kind: "table", range: "All rows!A1:Z8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 26 })).ndjson;
checks.suspicious = (await workbook.inspect({ kind: "table", range: "Top 50 suspicious!A1:M12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 13 })).ndjson;
checks.regression = (await workbook.inspect({ kind: "table", range: "Regression!A1:G12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 7 })).ndjson;
checks.errors = (await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
})).ndjson;

const previewDir = path.join(root, ".codex_tmp", "benchmark_after", "previews");
await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range, fileName] of [
  ["Summary", "A1:I40", "summary.png"],
  ["All rows", "A1:Z20", "all_rows.png"],
  ["Top 50 suspicious", "A1:M15", "suspicious.png"],
  ["Regression", "A1:G12", "regression.png"],
]) {
  const image = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName), new Uint8Array(await image.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
await fs.writeFile(path.join(root, ".codex_tmp", "benchmark_after", "workbook_checks.json"), JSON.stringify(checks, null, 2));
console.log(JSON.stringify({ outputPath, rows: diffRows.length, suspicious: suspiciousRows.length, regressions: regressionRows.length }));
