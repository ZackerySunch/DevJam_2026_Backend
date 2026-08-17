// Helper for scripts/fetch_cables.py: imports a JS module file and prints
// its default export as JSON, so Python doesn't have to regex-parse
// minified JS to pull the cable data back out.
const path = process.argv[2];
const mod = await import("file://" + path.replace(/\\/g, "/"));
process.stdout.write(JSON.stringify(mod.default));
