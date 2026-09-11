import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "C:/Users/Principale/Documents/ChatGPT/vector_db_pt";
const workDir = path.join(root, ".codex_tmp", "audit_mpn_fix1");
const outputDir = path.join(root, "outputs", "clima_audit_fix1_20260911");
const outputPath = path.join(outputDir, "audit_da_compilare_MPN_PT26_CLIMA_PROD_2_FIX1_PARTIAL_2000.xlsx");
const lines = (await fs.readFile(path.join(workDir, "audit_results.jsonl"), "utf8"))
  .split(/\r?\n/).filter(Boolean);
const results = lines.map((line) => JSON.parse(line));

const headers = [
  "Nome", "MPN", "CODICI_PT", "CODICI_PT_MAIN_UNIT", "CODICI_PT_ACCESSORI",
  "CONFIGURATION_STATUS", "MPN_FINAL_ALLOWED", "MASTER_RESOLUTION_TYPE", "DATASET_RELEASE",
  "MAIN_UNIT_MATCH_STATUS", "ACCESSORY_STATUS", "LEGACY_FALLBACK_USED",
  "MASTER_CONFIGURATION_KEY", "RUNTIME_MS", "ERRORE",
  "FEEDBACK_ESITO", "FEEDBACK_CODICI_PT_CORRETTI", "FEEDBACK_NOTE", "MPN_ORIGINALE",
];
const rows = results.map((row) => [
  row.title, row.mpn, row.codici_pt, row.codici_pt_main_unit, row.codici_pt_accessori,
  row.configuration_status, row.mpn_final_allowed, row.master_resolution_type, row.dataset_release || "",
  row.main_unit_match_status, row.accessory_status, row.legacy_fallback_used,
  row.master_configuration_key || "", row.runtime_ms, row.error,
  "", "", "", row.original_mpn == null ? "" : String(row.original_mpn),
]);

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Audit MPN");
sheet.showGridLines = false;
sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
sheet.getRangeByIndexes(1, 0, rows.length, headers.length).values = rows;

const header = sheet.getRangeByIndexes(0, 0, 1, headers.length);
header.format = {
  fill: "#1E3A5F",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
};
header.format.rowHeight = 34;
const body = sheet.getRangeByIndexes(1, 0, rows.length, headers.length);
body.format.font = { name: "Arial", size: 10, color: "#1F2937" };
body.format.verticalAlignment = "top";
sheet.getRangeByIndexes(1, 13, rows.length, 1).format.numberFormat = "0.00";
sheet.getRangeByIndexes(1, 6, rows.length, 1).format.horizontalAlignment = "center";
sheet.getRangeByIndexes(1, 11, rows.length, 1).format.horizontalAlignment = "center";

sheet.getRange(`P2:P${rows.length + 1}`).dataValidation = {
  rule: { type: "list", values: ["CORRETTO", "ERRATO", "DA_VERIFICARE", "NON_APPLICABILE"] },
};
sheet.getRange(`P2:R${rows.length + 1}`).format.fill = "#FFF2CC";
sheet.getRange(`P2:R${rows.length + 1}`).format.font = { name: "Arial", size: 10, color: "#7F6000" };
sheet.getRange(`O2:O${rows.length + 1}`).conditionalFormats.add("notContainsBlanks", {
  format: { fill: "#FCE8E6", font: { color: "#B91C1C", bold: true } },
});
sheet.getRange(`G2:G${rows.length + 1}`).conditionalFormats.add("cellIs", {
  operator: "equal", formula: "FALSE", format: { fill: "#FFF2CC", font: { color: "#9C5700" } },
});

sheet.freezePanes.freezeRows(1);
sheet.freezePanes.freezeColumns(1);
sheet.getRange("A:A").format.columnWidth = 72;
sheet.getRange("B:E").format.columnWidth = 30;
sheet.getRange("F:F").format.columnWidth = 30;
sheet.getRange("G:G").format.columnWidth = 18;
sheet.getRange("H:M").format.columnWidth = 28;
sheet.getRange("N:N").format.columnWidth = 14;
sheet.getRange("O:O").format.columnWidth = 36;
sheet.getRange("P:P").format.columnWidth = 20;
sheet.getRange("Q:Q").format.columnWidth = 34;
sheet.getRange("R:R").format.columnWidth = 42;
sheet.getRange("S:S").format.columnWidth = 28;
sheet.getRange(`A2:A${rows.length + 1}`).format.wrapText = true;
sheet.getRange(`F2:M${rows.length + 1}`).format.wrapText = true;
sheet.getRange(`O2:S${rows.length + 1}`).format.wrapText = true;
const table = sheet.tables.add(`A1:S${rows.length + 1}`, true, "AuditMPNFix1Table");
table.style = "TableStyleMedium2";

workbook.recalculate();
const checks = {};
checks.first = (await workbook.inspect({ kind: "table", range: "Audit MPN!A1:S8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 19 })).ndjson;
const middle = Math.floor(rows.length / 2) + 1;
checks.middle = (await workbook.inspect({ kind: "table", range: `Audit MPN!A${middle}:S${middle + 2}`, include: "values,formulas", tableMaxRows: 3, tableMaxCols: 19 })).ndjson;
checks.last = (await workbook.inspect({ kind: "table", range: `Audit MPN!A${rows.length}:S${rows.length + 1}`, include: "values,formulas", tableMaxRows: 2, tableMaxCols: 19 })).ndjson;
checks.errors = (await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
})).ndjson;

await fs.mkdir(path.join(workDir, "previews"), { recursive: true });
for (const [range, name] of [["A1:J18", "audit_left.png"], ["K1:S18", "audit_right.png"]]) {
  const preview = await workbook.render({ sheetName: "Audit MPN", range, scale: 1, format: "png" });
  await fs.writeFile(path.join(workDir, "previews", name), new Uint8Array(await preview.arrayBuffer()));
}
await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await (await import("@oai/artifact-tool")).FileBlob.load(outputPath));
checks.saved = (await saved.inspect({ kind: "workbook,sheet,table", maxChars: 5000, tableMaxRows: 3, tableMaxCols: 19 })).ndjson;
await fs.writeFile(path.join(workDir, "workbook_checks.json"), JSON.stringify(checks, null, 2));
console.log(JSON.stringify({ outputPath, rows: rows.length, columns: headers.length }));
