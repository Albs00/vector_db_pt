import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = "C:/Users/Principale/Documents/ChatGPT/vector_db_pt/reports/clima_ab/before_after.xlsx";
const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 4000 });
const summary = await workbook.inspect({ kind: "table", range: "Summary!A1:I40", include: "values,formulas", tableMaxRows: 40, tableMaxCols: 10 });
const allRows = await workbook.inspect({ kind: "table", range: "All rows!A1:Z8", include: "values,formulas", tableMaxRows: 8, tableMaxCols: 26 });
const suspicious = await workbook.inspect({ kind: "table", range: "Top 50 suspicious!A1:M12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 13 });
const regression = await workbook.inspect({ kind: "table", range: "Regression!A1:G12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 7 });
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "saved workbook formula error scan",
});
const output = { sheets: sheets.ndjson, summary: summary.ndjson, allRows: allRows.ndjson, suspicious: suspicious.ndjson, regression: regression.ndjson, errors: errors.ndjson };
await fs.writeFile("C:/Users/Principale/Documents/ChatGPT/vector_db_pt/.codex_tmp/benchmark_after/saved_workbook_checks.json", JSON.stringify(output, null, 2));
console.log(JSON.stringify({ sheets: sheets.ndjson, errors: errors.ndjson }));
