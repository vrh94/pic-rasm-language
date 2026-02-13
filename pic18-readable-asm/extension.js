// PIC16/PIC18 Readable Assembly — VS Code Extension
// Provides inline autocomplete suggestions for .rasm files

const vscode = require("vscode");
const fs = require("fs");
const path = require("path");

/**
 * Load instruction map from a JSON file.
 * Returns an array of { readable, mnemonic, lang, family } objects.
 */
function loadInstructions(jsonPath, family) {
    if (!fs.existsSync(jsonPath)) return [];
    const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
    const items = [];
    for (const lang of ["en", "si"]) {
        if (!data[lang]) continue;
        for (const [readable, mnemonic] of Object.entries(data[lang])) {
            items.push({ readable, mnemonic, lang, family });
        }
    }
    return items;
}

/**
 * Build a category label from the mnemonic for grouping in the detail field.
 */
function categoryOf(entry) {
    const tags = [];
    tags.push(entry.family);
    tags.push(entry.lang === "en" ? "EN" : "SI");
    return tags.join(" · ");
}

/**
 * Create a CompletionItem for a single instruction entry.
 */
function makeCompletionItem(entry) {
    const item = new vscode.CompletionItem(
        entry.readable,
        vscode.CompletionItemKind.Function
    );
    item.detail = `${entry.mnemonic}  (${categoryOf(entry)})`;
    item.documentation = new vscode.MarkdownString(
        `**${entry.readable}** → \`${entry.mnemonic}\`\n\n` +
        `*${entry.family} — ${entry.lang === "en" ? "English" : "Slovenian"}*`
    );
    item.insertText = entry.readable;
    // Sort so English comes before Slovenian, PIC18 before PIC16
    const sortPrefix =
        (entry.family === "PIC18" ? "0" : "1") +
        (entry.lang === "en" ? "0" : "1");
    item.sortText = sortPrefix + entry.readable;
    return item;
}

function activate(context) {
    // Resolve instruction JSON paths — try multiple locations:
    //   1. Bundled inside the extension folder  (always works)
    //   2. Workspace root / instructions /      (dev-time convenience)
    //   3. One level up from extension dir      (legacy layout)
    const extDir = context.extensionPath;

    function findInstructionsDir() {
        // 1. Inside extension
        const bundled = path.join(extDir, "instructions");
        if (fs.existsSync(bundled)) return bundled;

        // 2. Workspace folders
        if (
            vscode.workspace.workspaceFolders &&
            vscode.workspace.workspaceFolders.length > 0
        ) {
            for (const wf of vscode.workspace.workspaceFolders) {
                const candidate = path.join(wf.uri.fsPath, "instructions");
                if (fs.existsSync(candidate)) return candidate;
            }
        }

        // 3. One level up (extension lives inside project root)
        const parentDir = path.join(extDir, "..", "instructions");
        if (fs.existsSync(parentDir)) return parentDir;

        return null;
    }

    const instrDir = findInstructionsDir();

    if (!instrDir) {
        console.warn(
            "PIC Readable ASM: instructions/ directory not found. " +
            "Autocomplete will be limited to directives only."
        );
    }

    const pic18Path = instrDir
        ? path.join(instrDir, "pic18_instructions.json")
        : null;
    const pic16Path = instrDir
        ? path.join(instrDir, "pic16_instructions.json")
        : null;

    const allEntries = [
        ...(pic18Path ? loadInstructions(pic18Path, "PIC18") : []),
        ...(pic16Path ? loadInstructions(pic16Path, "PIC16") : []),
    ];

    // Pre-build CompletionItem objects once
    const completionItems = allEntries.map(makeCompletionItem);

    // ── Assignment-syntax completions (wreg = ..., dest = src) ──
    const assignmentItems = [];

    // wreg = <value>  (MOVLW)
    const wregItem = new vscode.CompletionItem(
        "wreg =",
        vscode.CompletionItemKind.Snippet
    );
    wregItem.detail = "MOVLW  (assign literal to W register)";
    wregItem.documentation = new vscode.MarkdownString(
        "**wreg = <value>** → `MOVLW <value>`\n\n" +
        "Loads a literal value into the W register.\n\n" +
        "Example: `wreg = 0x04`"
    );
    wregItem.insertText = new vscode.SnippetString("wreg = ${1:0x00}");
    wregItem.sortText = "00wreg";
    assignmentItems.push(wregItem);

    // <dest> = wreg  (MOVWF)
    const movwfItem = new vscode.CompletionItem(
        "<reg> = wreg",
        vscode.CompletionItemKind.Snippet
    );
    movwfItem.detail = "MOVWF  (assign W to register)";
    movwfItem.documentation = new vscode.MarkdownString(
        "**<dest> = wreg** → `MOVWF <dest>`\n\n" +
        "Moves W register to a file register.\n\n" +
        "Example: `PORTB = wreg`"
    );
    movwfItem.insertText = new vscode.SnippetString("${1:REG} = wreg");
    movwfItem.sortText = "00movwf";
    assignmentItems.push(movwfItem);

    // <dest> = <src>  (MOVFF)
    const movffItem = new vscode.CompletionItem(
        "<dest> = <src>",
        vscode.CompletionItemKind.Snippet
    );
    movffItem.detail = "MOVFF  (assign register to register)";
    movffItem.documentation = new vscode.MarkdownString(
        "**<dest> = <src>** → `MOVFF <src>, <dest>`\n\n" +
        "Copies one file register to another.\n\n" +
        "Example: `PORTB = PORTA`"
    );
    movffItem.insertText = new vscode.SnippetString("${1:DEST} = ${2:SRC}");
    movffItem.sortText = "00movff";
    assignmentItems.push(movffItem);

    // Also build a set of common assembler directives
    const directives = [
        "ORG", "EQU", "CONFIG", "LIST", "END", "DB", "DW", "DT",
        "#include", "#define", "#ifdef", "#ifndef", "#endif", "#else",
        "CBLOCK", "ENDC", "BANKSEL", "PAGESEL", "PROCESSOR",
        "RADIX", "CONSTANT", "VARIABLE", "EXTERN", "GLOBAL",
        "CODE", "UDATA", "UDATA_SHR", "UDATA_ACS", "IDATA", "ACCESS",
        "__CONFIG", "__IDLOCS", "ERRORLEVEL", "MESSG", "SUBTITLE", "TITLE",
    ];
    const directiveItems = directives.map((d) => {
        const item = new vscode.CompletionItem(d, vscode.CompletionItemKind.Keyword);
        item.detail = "Directive";
        item.sortText = "2" + d; // after instructions
        return item;
    });

    // Register the completion provider for the pic18rasm language
    const provider = vscode.languages.registerCompletionItemProvider(
        { language: "pic18rasm", scheme: "file" },
        {
            provideCompletionItems(document, position, token, ctx) {
                // Get the text on the current line up to the cursor
                const lineText = document
                    .lineAt(position)
                    .text.substring(0, position.character);

                // Don't suggest inside comments
                const semiIdx = lineText.indexOf(";");
                if (semiIdx !== -1 && position.character > semiIdx) {
                    return [];
                }

                // Return all items — VS Code filters by typed prefix automatically
                return [...assignmentItems, ...completionItems, ...directiveItems];
            },
        },
        // Trigger on every letter, underscore, and = for assignment syntax
        ..."abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_#="
    );

    context.subscriptions.push(provider);

    console.log(
        `PIC16/PIC18 Readable Assembly — autocomplete activated ` +
        `(${allEntries.length} instructions, ${directives.length} directives` +
        `${instrDir ? ", from " + instrDir : ", NO instruction JSONs found"})`
    );
}

function deactivate() {}

module.exports = { activate, deactivate };
