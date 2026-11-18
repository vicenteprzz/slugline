// Runs Slugline's own Python (slugline.zip, built by tools/build_calculator.py)
// in the browser with Pyodide, off the page's thread. The script is read here and
// never sent anywhere.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const GLUE = `
import io, json
from slugline import pdf_import, fdx_import
from slugline.estimate import estimate

async def run(kind, data, market):
    try:
        raw = bytes(data.to_py())
        if kind == "pdf":
            import micropip
            await micropip.install("pypdf==5.1.0")
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text = "\\f".join(p.extract_text(extraction_mode="layout") for p in reader.pages)
            if pdf_import.is_scanned(text):
                return json.dumps({"error": "scanned"})
            text = pdf_import.pdf_text_to_fountain(text)
        elif kind == "fdx":
            text = fdx_import.fdx_to_fountain(raw)
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
        return json.dumps({"result": estimate(text, market)})
    except ValueError:
        return json.dumps({"error": "notscript"})
    except Exception as e:
        return json.dumps({"error": "failed", "detail": type(e).__name__})
`;

let ready = null;
function boot() {
  if (!ready) {
    ready = (async () => {
      const py = await loadPyodide({ indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/" });
      await py.loadPackage("micropip");
      const zip = await fetch("slugline.zip").then((r) => r.arrayBuffer());
      py.unpackArchive(zip, "zip");
      await py.runPythonAsync(GLUE);
      return py.globals.get("run");
    })();
  }
  return ready;
}

self.onmessage = async (e) => {
  const { id, kind, data, market } = e.data;
  try {
    const run = await boot();
    if (kind === "boot") return self.postMessage({ id, ready: true });
    const out = await run(kind, data, market);
    self.postMessage({ id, ...JSON.parse(out) });
  } catch (err) {
    self.postMessage({ id, error: "load" });
  }
};
