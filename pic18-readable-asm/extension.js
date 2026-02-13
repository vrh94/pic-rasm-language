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
    // Resolve instruction JSON paths relative to this extension folder
    const extDir = context.extensionPath;
    // JSON files live in the project root's instructions/ folder,
    // which is one level up from the extension folder.
    const instrDir = path.join(extDir, "..", "instructions");

    const pic18Path = path.join(instrDir, "pic18_instructions.json");
    const pic16Path = path.join(instrDir, "pic16_instructions.json");

    const allEntries = [
        ...loadInstructions(pic18Path, "PIC18"),
        ...loadInstructions(pic16Path, "PIC16"),
    ];

    // Pre-build CompletionItem objects once
    const completionItems = allEntries.map(makeCompletionItem);

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
                return [...completionItems, ...directiveItems];
            },
        },
        // Trigger on every letter and underscore for smooth inline suggestions
        ..."abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_#"
    );

    context.subscriptions.push(provider);

    console.log("PIC16/PIC18 Readable Assembly — autocomplete activated");
}

function deactivate() {}

module.exports = { activate, deactivate };
