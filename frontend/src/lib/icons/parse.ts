// Strict-allowlist SVG parser. Hand-rolled, zero-dependency, build-time
// only. Reads an SVG file as a UTF-8 string and either returns a typed
// `Icon` structure or throws an `IconParseError` with a precise
// `file:line:column` location and a one-line human explanation.
//
// Threat model (per the chart plan §1.3):
//   * The input is a contributor-supplied SVG file committed to the repo.
//   * The danger is that the file might smuggle <script>, onload=…,
//     <foreignObject>, xlink:href, or any other vector that would execute
//     in the citizen's bundle. Rejecting at build is the right place: it
//     fails the contributor's PR, not the citizen's page load.
//   * The parser is deliberately small. It does NOT handle CDATA sections,
//     processing instructions other than `<?xml ?>`, DOCTYPE, or HTML-style
//     unquoted attributes. Lucide SVGs don't use any of these; if a future
//     icon source does, that file gets cleaned by hand before commit.
//
// Why hand-rolled instead of htmlparser2 / parse5 / linkedom:
//   * One new devDependency = one new `bun.lock` churn, one new transitive
//     graph to audit. The chart plan's §1.3 review (Fowler, 2026-05-20)
//     traded dep weight against parser simplicity and chose the latter
//     because the allowlist is tiny (8 element names, ~22 attribute names)
//     and the threat surface is fully closed by build-time rejection.
//   * Hand-rolled means the rejection logic is auditable in 200 lines that
//     a fresh reviewer can hold in their head. A third-party HTML parser
//     is auditable in 5000+ lines that no human reviews.

import {
  ALLOWED_ELEMENTS,
  ALLOWED_ATTRS,
  TOLERATED_ROOT_ATTRS,
  FORBIDDEN_ELEMENTS,
  FORBIDDEN_ATTR_PATTERNS,
} from "./allowlist";
import type { Icon, IconElement, IconElementName, IconAttributes } from "./types";

export class IconParseError extends Error {
  constructor(
    public readonly file: string,
    public readonly line: number,
    public readonly column: number,
    public readonly reason: string
  ) {
    super(`${file}:${line}:${column}  ${reason}`);
    this.name = "IconParseError";
  }
}

// Internal token. The tokenizer emits a stream of these from the input
// string; `parseIcon` then walks the stream to build the typed structure.
type Token =
  | { kind: "open"; name: string; attrs: ReadonlyMap<string, string>; selfClosing: boolean; line: number; col: number }
  | { kind: "close"; name: string; line: number; col: number }
  | { kind: "text"; value: string; line: number; col: number }
  | { kind: "comment"; line: number; col: number }
  | { kind: "decl"; line: number; col: number }; // <?xml …?>

// Walks `src` character by character. Tracks line + column for diagnostics.
// Returns the next token plus the new index, or null at end of input.
function nextToken(src: string, index: number, line: number, col: number): { token: Token | null; index: number; line: number; col: number } {
  if (index >= src.length) return { token: null, index, line, col };

  // Text node (between tags). Treat as content; the parser will reject any
  // non-whitespace text inside an icon SVG. Whitespace is dropped.
  if (src[index] !== "<") {
    const start = index;
    while (index < src.length && src[index] !== "<") {
      if (src[index] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
      index++;
    }
    return {
      token: { kind: "text", value: src.slice(start, index), line, col },
      index,
      line,
      col,
    };
  }

  const tagStartLine = line;
  const tagStartCol = col;

  // Consume `<`.
  index++;
  col++;

  // Comment: <!-- … -->
  if (src.startsWith("!--", index)) {
    const end = src.indexOf("-->", index + 3);
    if (end < 0) throw new IconParseError("<unknown>", tagStartLine, tagStartCol, "unterminated comment");
    // Advance line counter through the comment body.
    for (let i = index; i < end + 3; i++) {
      if (src[i] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
    }
    return { token: { kind: "comment", line: tagStartLine, col: tagStartCol }, index: end + 3, line, col };
  }

  // Declaration: <?xml … ?>
  if (src[index] === "?") {
    const end = src.indexOf("?>", index);
    if (end < 0) throw new IconParseError("<unknown>", tagStartLine, tagStartCol, "unterminated declaration");
    for (let i = index; i < end + 2; i++) {
      if (src[i] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
    }
    return { token: { kind: "decl", line: tagStartLine, col: tagStartCol }, index: end + 2, line, col };
  }

  // DOCTYPE — reject up front. Lucide doesn't emit one; if a contributor's
  // file has one, they should remove it (DOCTYPE has no meaning in inline
  // SVG-in-HTML anyway).
  if (src.startsWith("!DOCTYPE", index) || src.startsWith("!doctype", index)) {
    throw new IconParseError("<unknown>", tagStartLine, tagStartCol, "DOCTYPE is not allowed — strip it from the file");
  }

  // Closing tag: </name>
  if (src[index] === "/") {
    index++;
    col++;
    const nameStart = index;
    while (index < src.length && src[index] !== ">" && !/\s/.test(src[index])) {
      index++;
      col++;
    }
    const name = src.slice(nameStart, index);
    while (index < src.length && /\s/.test(src[index])) {
      if (src[index] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
      index++;
    }
    if (src[index] !== ">") throw new IconParseError("<unknown>", tagStartLine, tagStartCol, "malformed closing tag");
    index++;
    col++;
    return { token: { kind: "close", name, line: tagStartLine, col: tagStartCol }, index, line, col };
  }

  // Opening tag: <name attr="val" …> or <name … />
  const nameStart = index;
  while (index < src.length && !/[\s/>]/.test(src[index])) {
    index++;
    col++;
  }
  const name = src.slice(nameStart, index);
  const attrs = new Map<string, string>();

  // Attribute parsing loop.
  while (index < src.length) {
    // Skip whitespace.
    while (index < src.length && /\s/.test(src[index])) {
      if (src[index] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
      index++;
    }
    if (index >= src.length) throw new IconParseError("<unknown>", tagStartLine, tagStartCol, "unterminated opening tag");
    if (src[index] === ">") {
      index++;
      col++;
      return { token: { kind: "open", name, attrs, selfClosing: false, line: tagStartLine, col: tagStartCol }, index, line, col };
    }
    if (src[index] === "/" && src[index + 1] === ">") {
      index += 2;
      col += 2;
      return { token: { kind: "open", name, attrs, selfClosing: true, line: tagStartLine, col: tagStartCol }, index, line, col };
    }

    // Attribute name. Allow letters, digits, `-`, `:`, `_`.
    const attrNameStart = index;
    while (index < src.length && /[A-Za-z0-9:_-]/.test(src[index])) {
      index++;
      col++;
    }
    const attrName = src.slice(attrNameStart, index);
    if (!attrName) throw new IconParseError("<unknown>", tagStartLine, tagStartCol, `unexpected character '${src[index]}' in attribute list`);

    // Skip whitespace around `=`.
    while (index < src.length && /\s/.test(src[index])) {
      if (src[index] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
      index++;
    }
    if (src[index] !== "=") throw new IconParseError("<unknown>", tagStartLine, tagStartCol, `attribute '${attrName}' has no value (boolean attributes are not allowed)`);
    index++;
    col++;
    while (index < src.length && /\s/.test(src[index])) {
      if (src[index] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
      index++;
    }

    // Attribute value must be quoted.
    const quote = src[index];
    if (quote !== '"' && quote !== "'") throw new IconParseError("<unknown>", tagStartLine, tagStartCol, `attribute '${attrName}' value is not quoted`);
    index++;
    col++;
    const valStart = index;
    while (index < src.length && src[index] !== quote) {
      if (src[index] === "\n") {
        line++;
        col = 1;
      } else {
        col++;
      }
      index++;
    }
    if (index >= src.length) throw new IconParseError("<unknown>", tagStartLine, tagStartCol, `attribute '${attrName}' value is unterminated`);
    const value = src.slice(valStart, index);
    index++;
    col++;

    attrs.set(attrName, value);
  }

  throw new IconParseError("<unknown>", tagStartLine, tagStartCol, "unterminated opening tag");
}

// Top-level parse. `src` is the SVG file contents; `file` is the relative
// path (or any human-readable label) used in error messages.
export function parseIcon(src: string, file: string, name: string): Icon {
  const tokens: Token[] = [];
  let index = 0;
  let line = 1;
  let col = 1;
  try {
    for (;;) {
      const r = nextToken(src, index, line, col);
      if (!r.token) break;
      tokens.push(r.token);
      index = r.index;
      line = r.line;
      col = r.col;
    }
  } catch (err) {
    if (err instanceof IconParseError) {
      throw new IconParseError(file, err.line, err.column, err.reason);
    }
    throw err;
  }

  // Find the root <svg>. Tolerate leading decl/comment/whitespace text.
  let i = 0;
  while (i < tokens.length) {
    const t = tokens[i];
    if (t.kind === "decl" || t.kind === "comment") {
      i++;
      continue;
    }
    if (t.kind === "text" && t.value.trim() === "") {
      i++;
      continue;
    }
    break;
  }
  if (i >= tokens.length) throw new IconParseError(file, 1, 1, "file contains no SVG element");
  const root = tokens[i];
  if (root.kind !== "open" || root.name !== "svg") {
    throw new IconParseError(file, root.line, root.col, "root element must be <svg>");
  }

  // Validate root attributes. `viewBox` is required; everything else must
  // be in the tolerated-root set or it's a hard reject.
  const viewBox = root.attrs.get("viewBox");
  if (!viewBox) throw new IconParseError(file, root.line, root.col, "root <svg> is missing required attribute viewBox");
  for (const [attrName] of root.attrs) {
    if (attrName === "viewBox") continue;
    rejectForbiddenAttr(file, root.line, root.col, attrName);
    if (!TOLERATED_ROOT_ATTRS.has(attrName)) {
      throw new IconParseError(file, root.line, root.col, `disallowed attribute on root <svg>: '${attrName}'`);
    }
  }

  // Parse children recursively. Cursor stops at the matching </svg>.
  const { children, cursor } = parseChildren(tokens, i + 1, file, "svg");
  // After the matching </svg> only whitespace / comment / decl are allowed.
  for (let j = cursor; j < tokens.length; j++) {
    const t = tokens[j];
    if (t.kind === "comment" || t.kind === "decl") continue;
    if (t.kind === "text" && t.value.trim() === "") continue;
    throw new IconParseError(file, t.line, t.col, `unexpected content after closing </svg>`);
  }

  return { name, viewBox, children };
}

function parseChildren(tokens: Token[], start: number, file: string, parentName: string): { children: IconElement[]; cursor: number } {
  const children: IconElement[] = [];
  let i = start;
  while (i < tokens.length) {
    const t = tokens[i];
    if (t.kind === "close") {
      if (t.name !== parentName) throw new IconParseError(file, t.line, t.col, `mismatched closing tag </${t.name}> (expected </${parentName}>)`);
      return { children, cursor: i + 1 };
    }
    if (t.kind === "comment" || t.kind === "decl") {
      i++;
      continue;
    }
    if (t.kind === "text") {
      if (t.value.trim() !== "") {
        throw new IconParseError(file, t.line, t.col, "text content is not allowed inside an icon SVG");
      }
      i++;
      continue;
    }
    // t.kind === "open"
    if (FORBIDDEN_ELEMENTS.has(t.name)) {
      throw new IconParseError(file, t.line, t.col, `forbidden element <${t.name}> — see frontend/src/lib/icons/allowlist.ts`);
    }
    if (!ALLOWED_ELEMENTS.has(t.name as IconElementName)) {
      throw new IconParseError(file, t.line, t.col, `disallowed element <${t.name}> — allowlist: ${[...ALLOWED_ELEMENTS].join(", ")}`);
    }
    const attrs: Record<string, string> = {};
    for (const [aName, aVal] of t.attrs) {
      rejectForbiddenAttr(file, t.line, t.col, aName);
      if (!ALLOWED_ATTRS.has(aName)) {
        throw new IconParseError(file, t.line, t.col, `disallowed attribute '${aName}' on <${t.name}> — see allowlist.ts`);
      }
      attrs[aName] = aVal;
    }
    if (t.selfClosing) {
      children.push({ name: t.name as IconElementName, attrs, children: [] });
      i++;
      continue;
    }
    const { children: nested, cursor } = parseChildren(tokens, i + 1, file, t.name);
    children.push({ name: t.name as IconElementName, attrs, children: nested });
    i = cursor;
  }
  throw new IconParseError(file, tokens[start - 1]?.line ?? 1, tokens[start - 1]?.col ?? 1, `unclosed element <${parentName}>`);
}

function rejectForbiddenAttr(file: string, line: number, col: number, attrName: string): void {
  for (const pat of FORBIDDEN_ATTR_PATTERNS) {
    if (pat.test(attrName)) {
      throw new IconParseError(file, line, col, `forbidden attribute '${attrName}' (pattern ${pat}) — see allowlist.ts`);
    }
  }
}
