import { describe, expect, it } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown - 安全性", () => {
  it("转义 script 标签，不产生可执行 HTML", () => {
    const html = renderMarkdown('<script>alert("xss")</script>');
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("转义 img onerror 注入", () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">');
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
  });

  it("阻止 javascript: 伪协议链接", () => {
    const html = renderMarkdown('[点我](javascript:alert(1))');
    // 不生成 anchor，伪协议只作为纯文本残留，无法被点击触发
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("href");
  });

  it("阻止 data: 协议链接", () => {
    const html = renderMarkdown('[x](data:text/html,alert(1))');
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("href");
  });

  it("允许 http/https 链接并加固 rel 属性", () => {
    const html = renderMarkdown("[Yahoo](https://finance.yahoo.com)");
    expect(html).toContain('href="https://finance.yahoo.com"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('target="_blank"');
  });

  it("转义属性中的引号，防止属性逃逸", () => {
    const html = renderMarkdown('普通文本 " 和 \' 引号');
    expect(html).toContain("&quot;");
    expect(html).toContain("&#39;");
  });

  it("代码块内的 HTML 同样被转义", () => {
    const html = renderMarkdown("```\n<script>bad()</script>\n```");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });
});

describe("renderMarkdown - 基础语法", () => {
  it("空输入返回空串", () => {
    expect(renderMarkdown("")).toBe("");
  });

  it("渲染各级标题", () => {
    expect(renderMarkdown("# 一级")).toContain('<h1 class="md-h1">一级</h1>');
    expect(renderMarkdown("### 三级")).toContain('<h3 class="md-h3">三级</h3>');
    expect(renderMarkdown("###### 六级")).toContain("<h6");
  });

  it("七个井号不再是标题", () => {
    expect(renderMarkdown("####### 不是标题")).not.toContain("<h7");
  });

  it("渲染粗体、斜体、粗斜体", () => {
    expect(renderMarkdown("**粗**")).toContain("<strong>粗</strong>");
    expect(renderMarkdown("*斜*")).toContain("<em>斜</em>");
    expect(renderMarkdown("***both***")).toContain("<strong><em>both</em></strong>");
  });

  it("渲染删除线", () => {
    expect(renderMarkdown("~~废弃~~")).toContain("<del>废弃</del>");
  });

  it("渲染行内代码", () => {
    expect(renderMarkdown("使用 `MA60` 判断")).toContain("<code>MA60</code>");
  });

  it("行内代码内的星号不被当作强调", () => {
    const html = renderMarkdown("`a * b * c`");
    expect(html).toContain("<code>a * b * c</code>");
    expect(html).not.toContain("<em>");
  });

  it("渲染围栏代码块并保留语言标记", () => {
    const html = renderMarkdown("```python\nx = 1\n```");
    expect(html).toContain('class="lang-python"');
    expect(html).toContain("x = 1");
  });

  it("未闭合的代码块也能收尾", () => {
    const html = renderMarkdown("```\nunclosed content");
    expect(html).toContain("<pre");
    expect(html).toContain("unclosed content");
  });

  it("渲染无序列表", () => {
    const html = renderMarkdown("- 甲\n- 乙\n- 丙");
    expect(html).toContain('<ul class="md-list">');
    expect(html).toContain("<li>甲</li>");
    expect((html.match(/<li>/g) || []).length).toBe(3);
    expect(html).toContain("</ul>");
  });

  it("渲染有序列表", () => {
    const html = renderMarkdown("1. 第一\n2. 第二");
    expect(html).toContain('<ol class="md-list">');
    expect(html).toContain("<li>第一</li>");
  });

  it("有序与无序列表切换时正确闭合", () => {
    const html = renderMarkdown("- a\n1. b");
    expect(html).toContain("</ul>");
    expect(html).toContain("<ol");
  });

  it("渲染引用块", () => {
    const html = renderMarkdown("> 这是引用");
    expect(html).toContain('<blockquote class="md-quote">');
    expect(html).toContain("这是引用");
    expect(html).toContain("</blockquote>");
  });

  it("渲染水平分割线", () => {
    expect(renderMarkdown("---")).toContain("<hr />");
    expect(renderMarkdown("***")).toContain("<hr />");
  });

  it("渲染普通段落", () => {
    expect(renderMarkdown("一段文字")).toContain("<p>一段文字</p>");
  });
});

describe("renderMarkdown - 表格", () => {
  it("渲染完整表格", () => {
    const md = [
      "| 行权价 | 权利金 |",
      "| --- | --- |",
      "| 300 | 2.50 |",
      "| 295 | 1.80 |",
    ].join("\n");
    const html = renderMarkdown(md);

    expect(html).toContain('<table class="md-table">');
    expect(html).toContain("<th>行权价</th>");
    expect(html).toContain("<td>300</td>");
    expect((html.match(/<tr>/g) || []).length).toBe(3); // 表头 + 2 行
  });

  it("表格单元格内支持行内格式", () => {
    const md = "| 名称 |\n| --- |\n| **加粗** |";
    expect(renderMarkdown(md)).toContain("<strong>加粗</strong>");
  });

  it("缺少分隔行时不识别为表格", () => {
    const html = renderMarkdown("| a | b |\n| c | d |");
    expect(html).not.toContain("<table");
  });

  it("表格后的内容正常渲染", () => {
    const md = "| a |\n| --- |\n| 1 |\n\n后续段落";
    const html = renderMarkdown(md);
    expect(html).toContain("<table");
    expect(html).toContain("<p>后续段落</p>");
  });
});

describe("renderMarkdown - 组合场景", () => {
  it("渲染典型的 LLM 投资建议输出", () => {
    const md = [
      "## 结论",
      "",
      "**当前不是好价格**，建议观望。",
      "",
      "### 依据",
      "",
      "- 现价距 52 周高点仅 3%",
      "- RSI 为 `65`，接近超买",
      "",
      "> 依据你笔记中的纪律：只在 RSI < 40 时建仓",
      "",
      "| 策略 | 行权价 | 权利金 |",
      "| --- | --- | --- |",
      "| Sell Put | 300 | 2.50 |",
      "",
      "---",
      "",
      "风险提示：以上不构成投资建议。",
    ].join("\n");

    const html = renderMarkdown(md);

    expect(html).toContain("<h2");
    expect(html).toContain("<h3");
    expect(html).toContain("<strong>当前不是好价格</strong>");
    expect(html).toContain("<ul");
    expect(html).toContain("<code>65</code>");
    expect(html).toContain("<blockquote");
    expect(html).toContain("<table");
    expect(html).toContain("<hr />");
    expect(html).toContain("风险提示");
  });

  it("流式渲染的中间态不产生异常", () => {
    // 模拟 SSE 逐块到达时的不完整 markdown
    const partials = ["## 结", "## 结论\n\n**当前", "## 结论\n\n**当前不是**"];
    for (const p of partials) {
      expect(() => renderMarkdown(p)).not.toThrow();
    }
  });
});
