#!/usr/bin/env node
// vendored-from: https://github.com/cuhawk/tlxkull
// upstream-path: tlx/modules/js_analyzer/deobfuscate_wrapper.js
// upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
// imported-on:   2026-05-22
// license:       proprietary — see upstream repo
// modifications: none

/**
 * Thin wrapper: reads JS file, runs webcrack, writes deobfuscated output.
 * Called by ast_bridge.py when deobfuscate=True.
 *
 * Usage: node deobfuscate_wrapper.js <input.js> <output.js>
 *
 * On webcrack failure falls back to copying original source so pipeline
 * continues. Always exits 0 unless arguments are missing.
 */

const fs = require('fs');
const { webcrack } = require('webcrack');

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
    console.error('usage: node deobfuscate_wrapper.js <input.js> <output.js>');
    process.exit(2);
}

(async () => {
    const source = fs.readFileSync(inputPath, 'utf8');
    try {
        const result = await webcrack(source);
        fs.writeFileSync(outputPath, result.code, 'utf8');
        if (result.map) {
            const mapPath = outputPath + '.map';
            fs.writeFileSync(mapPath, JSON.stringify(result.map), 'utf8');
            console.error(`sourcemap: ${mapPath}`);
        } else {
            console.error('sourcemap: none');
        }
        console.error(`deobfuscated: ${inputPath} -> ${outputPath}`);
    } catch (err) {
        console.error('sourcemap: none');
        console.error(`webcrack failed on ${inputPath}: ${err.message}`);
        fs.writeFileSync(outputPath, source, 'utf8');
        process.exit(0);
    }
})();
