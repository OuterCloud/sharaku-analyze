/**
 * 轻量 Markdown 渲染器
 *
 * 安全设计：先转义全部 HTML 实体，再应用格式化规则。这样即使 LLM 输出或知识库
 * 文档中含有 HTML/脚本片段，也不会被当作标签执行，无需引入 sanitizer 依赖。
 *
 * 支持的语法：标题、粗体、斜体、行内代码、围栏代码块、有序/无序列表、
 * 引用块、表格、水平分割线、链接（仅 http/https）。
 */

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 行内格式化（在 HTML 已转义的文本上操作） */
function renderInline(text: string): string {
  let out = text;

  // 行内代码优先处理，避免其中的 * _ 被误当作强调
  const codeSlots: string[] = [];
  out = out.replace(/`([^`]+)`/g, (_, code) => {
    codeSlots.push(`<code>${code}</code>`);
    return `\u0000CODE${codeSlots.length - 1}\u0000`;
  });

  // 链接 [text](url) — 仅允许 http/https，防止 javascript: 伪协议
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) =>
    `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
  );

  // 粗斜体 / 粗体 / 斜体
  out = out.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");

  // 删除线
  out = out.replace(/~~([^~]+)~~/g, "<del>$1</del>");

  // 还原行内代码
  out = out.replace(/\u0000CODE(\d+)\u0000/g, (_, i) => codeSlots[Number(i)]);

  return out;
}

interface TableBlock {
  header: string[];
  rows: string[][];
}

function renderTable(tbl: TableBlock): string {
  const head = tbl.header.map((c) => `<th>${renderInline(c)}</th>`).join("");
  const body = tbl.rows
    .map((r) => `<tr>${r.map((c) => `<td>${renderInline(c)}</td>`).join("")}</tr>`)
    .join("");
  return `<table class="md-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function splitTableRow(line: string): string[] {
  return line
    .replace(/^\s*\|/, "")
    .replace(/\|\s*$/, "")
    .split("|")
    .map((c) => c.trim());
}

const TABLE_SEPARATOR = /^\s*\|?[\s:-]+\|[\s|:-]*$/;

export function renderMarkdown(markdown: string): string {
  if (!markdown) return "";

  const lines = escapeHtml(markdown).split("\n");
  const html: string[] = [];

  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeLang = "";
  let listType: "ul" | "ol" | null = null;
  let inQuote = false;

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };
  const closeQuote = () => {
    if (inQuote) {
      html.push("</blockquote>");
      inQuote = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trimEnd();

    // --- 围栏代码块 ---
    const fence = line.match(/^\s*```(\w*)\s*$/);
    if (fence) {
      if (inCodeBlock) {
        html.push(
          `<pre class="md-pre"><code${codeLang ? ` class="lang-${codeLang}"` : ""}>${codeLines.join("\n")}</code></pre>`
        );
        inCodeBlock = false;
        codeLines = [];
        codeLang = "";
      } else {
        closeList();
        closeQuote();
        inCodeBlock = true;
        codeLang = fence[1] || "";
      }
      continue;
    }
    if (inCodeBlock) {
      codeLines.push(raw);
      continue;
    }

    // --- 表格 ---
    if (line.includes("|") && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1])) {
      closeList();
      closeQuote();
      const header = splitTableRow(line);
      const rows: string[][] = [];
      i += 2; // 跳过表头与分隔行
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(splitTableRow(lines[i]));
        i++;
      }
      i--; // 回退一行，交给外层循环递增
      html.push(renderTable({ header, rows }));
      continue;
    }

    // --- 空行 ---
    if (!line.trim()) {
      closeList();
      closeQuote();
      continue;
    }

    // --- 水平分割线 ---
    if (/^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(line)) {
      closeList();
      closeQuote();
      html.push("<hr />");
      continue;
    }

    // --- 标题 ---
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList();
      closeQuote();
      const level = heading[1].length;
      html.push(`<h${level} class="md-h${level}">${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    // --- 引用块 ---
    const quote = line.match(/^\s*&gt;\s?(.*)$/);
    if (quote) {
      closeList();
      if (!inQuote) {
        html.push('<blockquote class="md-quote">');
        inQuote = true;
      }
      html.push(`<p>${renderInline(quote[1])}</p>`);
      continue;
    }
    closeQuote();

    // --- 列表 ---
    const ul = line.match(/^\s*[-*+]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (ul || ol) {
      const wanted: "ul" | "ol" = ul ? "ul" : "ol";
      if (listType !== wanted) {
        closeList();
        html.push(`<${wanted} class="md-list">`);
        listType = wanted;
      }
      html.push(`<li>${renderInline((ul || ol)![1])}</li>`);
      continue;
    }
    closeList();

    // --- 普通段落 ---
    html.push(`<p>${renderInline(line)}</p>`);
  }

  // 收尾：处理未闭合的块
  if (inCodeBlock && codeLines.length) {
    html.push(`<pre class="md-pre"><code>${codeLines.join("\n")}</code></pre>`);
  }
  closeList();
  closeQuote();

  return html.join("\n");
}
