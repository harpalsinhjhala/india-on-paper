// Step 1 of the pipeline: pull the CBDT PDFs and extract their page text.
//
// incometaxindia.gov.in sits behind Akamai, which returns 403 to scripted downloads
// (curl/requests). A normal browser session works, so this snippet runs in the browser
// console (or a browser-automation tool) on any https://www.incometaxindia.gov.in page.
// It returns JSON {name: [pageText, ...]}; save that as data/raw/extracted_pages.json
// and run `python scripts/split_pages.py` to write data/raw/text/*.txt.
//
// To add a new year: find its "Income Tax Return Statistics" page on
// https://www.incometaxindia.gov.in/direct-taxes-data, copy the PDF link, add it below.

const FILES = {
  "AY2014-15": "/documents/d/guest/income-tax-statistics-it-return-ay-2014-15-v1-1-pdf",
  "AY2015-16": "/documents/81799/15520974/Income-Tax-Statistics-IT-Return-AY-2015-16.pdf/f1af3715-cc44-43b9-6afb-b8dce068d235",
  "AY2016-17": "/documents/d/guest/income-tax-statistics-i-t-return-ay-2016-17-v1-pdf",
  "AY2017-18": "/documents/d/guest/income-tax-statistics-i-t-return-ay-2017-18-v1-pdf",
  "AY2018-19": "/documents/20117/0/IT-Return-Statistics-Assessment-Year-2018-19.pdf/d2fc64ff-cef5-c21c-32c9-8203afbe3172",
  "AY2019-20": "/documents/d/guest/income-tax-statistics-i-t-return-ay_2019-20-pdf",
  "AY2020-21": "/documents/d/guest/income-tax-statistics-i-t-return-ay_2020-21-pdf",
  "AY2021-22": "/documents/d/guest/income-tax-statistics-i-t-return-ay_2021-22-pdf",
  "AY2022-23": "/documents/d/guest/approved-version-income-tax-return-statistics-for-the-ay-2022-23-14062024-pdf",
  "AY2023-24": "/documents/d/guest/approved-version-income-tax-return-statistics-for-the-ay-2023-24-pdf",
  "TS": "/documents/d/guest/final-time-series-data-pdf",
};

const pdfjsLib = await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.min.mjs");
pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.worker.min.mjs";

// Rebuild text lines from positioned glyph runs. Runs that touch are joined, small gaps
// become a space, column-sized gaps become " | " so table cells stay separable.
async function extract(buf) {
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
  const pages = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const tc = await (await pdf.getPage(i)).getTextContent();
    const rows = {};
    for (const it of tc.items) {
      if (!it.str.trim()) continue;
      const y = Math.round(it.transform[5] / 3) * 3;
      (rows[y] = rows[y] || []).push({ x: it.transform[4], w: it.width, s: it.str, h: Math.abs(it.transform[0]) || 8 });
    }
    const lines = Object.keys(rows).map(Number).sort((a, b) => b - a).map(y => {
      let out = "", end = null;
      for (const it of rows[y].sort((a, b) => a.x - b.x)) {
        if (end === null) out = it.s;
        else { const gap = it.x - end; out += gap < it.h * 0.25 ? it.s : gap < it.h * 1.2 ? " " + it.s : " | " + it.s; }
        end = it.x + it.w;
      }
      return out.replace(/\s+/g, " ").trim();
    });
    pages.push(lines.join("\n"));
  }
  return pages;
}

const docs = {};
for (const [k, u] of Object.entries(FILES)) docs[k] = await extract(await (await fetch(u)).arrayBuffer());
JSON.stringify(docs);
