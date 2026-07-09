(function () {
  const siteData = window.THERAPEUTIC_SITE_DATA;
  const app = document.getElementById("app");
  const page = document.body.dataset.page;

  if (!app) {
    return;
  }

  if (!siteData) {
    app.replaceChildren(renderBuildNotice());
    return;
  }

  const fragment = document.createDocumentFragment();

  if (page === "index") {
    renderIndex(fragment);
  } else if (page === "pair") {
    renderPair(fragment);
  } else if (page === "background") {
    renderBackground(fragment);
  }

  app.replaceChildren(fragment);

  function renderIndex(target) {
    const totalPairs = siteData.categories.reduce((sum, category) => sum + category.pairs.length, 0);
    const totalFiles = siteData.categories.reduce(
      (sum, category) => sum + category.pairs.reduce((pairSum, pair) => pairSum + pair.files.length, 0),
      0
    );

    target.appendChild(pageTitle(
      "Dataset Viewer",
      "Therapeutic Inquiries Taxonomy",
      "Browse category pairs and compare the professional and unprofessional conversation variants side by side.",
      [
        `${siteData.categories.length} categories`,
        `${totalPairs} pairs`,
        `${totalFiles} JSON files`
      ]
    ));

    const list = el("section", "category-list");
    for (const category of siteData.categories) {
      const card = el("article", "category-card");
      const header = el("header");
      header.appendChild(el("h2", "", category.name));
      header.appendChild(el("p", "", `${category.pairs.length} pairs, ${countFiles(category)} files`));
      card.appendChild(header);

      const links = el("div", "pair-links");
      for (const pair of category.pairs) {
        const link = el("a", "button-link primary", `Pair ${pair.id}`);
        link.href = pairHref(category.slug, pair.id);
        links.appendChild(link);
      }
      card.appendChild(links);
      list.appendChild(card);
    }
    target.appendChild(list);
  }

  function renderPair(target) {
    const params = new URLSearchParams(window.location.search);
    const categorySlug = params.get("category");
    const pairId = params.get("pair");
    const category = siteData.categories.find((item) => item.slug === categorySlug);
    const pair = category ? category.pairs.find((item) => item.id === pairId) : null;

    if (!category || !pair) {
      const notice = el("section", "notice");
      notice.appendChild(el("h1", "", "Pair not found"));
      const paragraph = el("p");
      paragraph.append("Return to ");
      const link = el("a", "", "the landing page");
      link.href = "index.html";
      paragraph.appendChild(link);
      paragraph.append(".");
      notice.appendChild(paragraph);
      target.appendChild(notice);
      return;
    }

    document.title = `${category.name}`;

    const breadcrumb = el("div", "breadcrumb");
    const home = el("a", "", "Pairs");
    home.href = "index.html";
    breadcrumb.append(home, " / ", category.name, " / ", `Pair ${pair.id}`);
    target.appendChild(breadcrumb);

    target.appendChild(pageTitle(
      "Pair Comparison",
      `${category.name}`,
      "Compare any two files in this pair, then scan all professional and unprofessional editions.",
      [
        `${pair.files.length} files`,
        `${filesByPrefix(pair, "a").length} professional editions`,
        `${filesByPrefix(pair, "b").length} unprofessional editions`
      ]
    ));

    // target.appendChild(renderVariantLegend());
    renderFocusedComparison(target, pair);
    renderEditionSection(target, "Professional Editions", filesByPrefix(pair, "a"));
    renderEditionSection(target, "Unprofessional Editions", filesByPrefix(pair, "b"));
  }

  function renderFocusedComparison(target, pair) {
    const section = el("section", "section");
    section.appendChild(el("h2", "", "Focused Comparison"));

    const toolbar = el("div", "toolbar");
    const leftSelect = fileSelect(pair.files, "Left file", preferredFile(pair.files, "a"));
    const rightSelect = fileSelect(pair.files, "Right file", preferredFile(pair.files, "b"));
    toolbar.append(leftSelect.wrapper, rightSelect.wrapper);
    section.appendChild(toolbar);

    const grid = el("div", "comparison-grid");
    section.appendChild(grid);

    const render = () => {
      const left = pair.files.find((file) => file.filename === leftSelect.select.value);
      const right = pair.files.find((file) => file.filename === rightSelect.select.value);
      grid.replaceChildren(renderConversationCard(left), renderConversationCard(right));
    };

    leftSelect.select.addEventListener("change", render);
    rightSelect.select.addEventListener("change", render);
    render();
    target.appendChild(section);
  }

  function renderEditionSection(target, title, files) {
    const section = el("section", "section");
    section.appendChild(el("h2", "", title));
    const strip = el("div", "edition-strip");
    for (const file of files) {
      strip.appendChild(renderConversationCard(file));
    }
    section.appendChild(strip);
    target.appendChild(section);
  }

  function renderConversationCard(file) {
    const card = el("article", "conversation-card");
    const header = el("header");
    const titleLine = el("div", "card-title-line");
    titleLine.appendChild(el("div", "conversation-title", conversationTitle(file)));
    titleLine.appendChild(el("span", `badge ${file.condition}`, titleCase(file.condition)));
    header.appendChild(titleLine);
    header.appendChild(renderVariantBadges(file));
    card.appendChild(header);

    const turns = el("section", "turns");
    turns.appendChild(el("h3", "", "Conversation"));
    turns.appendChild(renderSpeakerKey());
    const turnList = el("div", "turn-list");
    for (const turn of file.turns || []) {
      const item = el("div", `turn ${turn.role}`);
      item.appendChild(el("div", "turn-text", turn.text));
      turnList.appendChild(item);
    }
    turns.appendChild(turnList);
    card.appendChild(turns);

    const reasons = el("section", "reasons");
    reasons.appendChild(el("h3", "", "Reasons"));
    const list = el("ul");
    for (const reason of file.metadata.reasons || []) {
      list.appendChild(el("li", "", reason));
    }
    reasons.appendChild(list);
    card.appendChild(reasons);

    return card;
  }

  function renderBackground(target) {
    document.title = "Background · Therapeutic Inquiries Taxonomy";
    target.appendChild(pageTitle(
      "Background",
      "Literature Review",
      "Background, summary, and references for the therapeutic inquiries taxonomy.",
      []
    ));

    const article = el("article", "background-article");
    for (const block of markdownBlocks(siteData.background || "")) {
      article.appendChild(block);
    }
    target.appendChild(article);
  }

  function renderBuildNotice() {
    const notice = el("section", "notice");
    notice.appendChild(el("h1", "", "Site data has not been generated"));
    notice.appendChild(el(
      "p",
      "",
      "Run `node scripts/build-pages.mjs` from the repository root, then open `_site/index.html`. The GitHub Pages workflow runs this build automatically before deployment.",
    ));
    return notice;
  }

  function pageTitle(eyebrow, title, lede, stats) {
    const header = el("section", "page-title");
    header.appendChild(el("div", "eyebrow", eyebrow));
    header.appendChild(el("h1", "", title));
    if (lede) {
      header.appendChild(el("p", "lede", lede));
    }
    if (stats.length) {
      const statRow = el("div", "stats");
      for (const stat of stats) {
        statRow.appendChild(el("span", "stat", stat));
      }
      header.appendChild(statRow);
    }
    return header;
  }

  function fileSelect(files, labelText, selectedFilename) {
    const wrapper = el("div", "field");
    const id = `select-${labelText.toLowerCase().replace(/\s+/g, "-")}`;
    const label = el("label", "", labelText);
    label.setAttribute("for", id);
    const select = el("select");
    select.id = id;
    for (const file of files) {
      const option = el("option", "", `${conversationTitle(file)} · ${titleCase(file.condition)}`);
      option.value = file.filename;
      if (file.filename === selectedFilename) {
        option.selected = true;
      }
      select.appendChild(option);
    }
    wrapper.append(label, select);
    return { wrapper, select };
  }

  function preferredFile(files, prefix) {
    const base = files.find((file) => file.filename === `${prefix}.json`);
    return (base || files.find((file) => file.stem.startsWith(prefix)) || files[0]).filename;
  }

  function filesByPrefix(pair, prefix) {
    return pair.files.filter((file) => file.stem === prefix || file.stem.startsWith(`${prefix}-`));
  }

  function countFiles(category) {
    return category.pairs.reduce((sum, pair) => sum + pair.files.length, 0);
  }

  function pairHref(categorySlug, pairId) {
    return `pair.html?category=${encodeURIComponent(categorySlug)}&pair=${encodeURIComponent(pairId)}`;
  }

  function renderVariantLegend() {
    const legend = el("section", "variant-legend");
    legend.appendChild(el("h2", "", "Variant Legend"));
    const row = el("div", "variant-row");
    for (const token of ["ha", "la", "hs", "ls"]) {
      row.appendChild(renderIndicator(token));
    }
    legend.appendChild(row);
    return legend;
  }

  function renderVariantBadges(file) {
    const variant = parseVariant(file.stem);
    const row = el("div", "variant-row");
    if (!variant.tokens.length) {
      row.appendChild(el("span", "indicator baseline", "Baseline"));
      return row;
    }
    for (const token of variant.tokens) {
      row.appendChild(renderIndicator(token));
    }
    return row;
  }

  function renderIndicator(token) {
    const details = variantTokenDetails(token);
    return el("span", `indicator ${details.kind}`, details.label);
  }

  function conversationTitle(file) {
    const variant = parseVariant(file.stem);
    if (!variant.tokens.length) {
      return "Baseline";
    }
    return variant.tokens.map((token) => variantTokenDetails(token).text).join(" + ");
  }

  function renderSpeakerKey() {
    const key = el("div", "speaker-key");
    key.appendChild(el("span", "speaker-pill assistant", "Assistant"));
    key.appendChild(el("span", "speaker-pill user", "User"));
    return key;
  }

  function parseVariant(stem) {
    const parts = stem.split("-").filter(Boolean);
    return {
      side: parts[0] || stem,
      tokens: parts.slice(1),
    };
  }

  function variantTokenDetails(token) {
    const level = token[0] === "h" ? "High" : token[0] === "l" ? "Low" : "";
    const dimension = token[1] === "a" ? "anthropomorphism" : token[1] === "s" ? "sycophancy" : "";
    const emoji = token[1] === "a" ? "🧑" : token[1] === "s" ? "👍" : "•";
    const arrow = token[0] === "h" ? "⬆️" : token[0] === "l" ? "⬇️" : "";

    if (!level || !dimension) {
      return {
        kind: "unknown",
        label: "Unknown variant",
        text: "Unknown variant",
      };
    }

    return {
      kind: dimension === "anthropomorphism" ? "anthropomorphism" : "sycophancy",
      label: `${emoji} ${arrow} ${level} ${dimension}`,
      text: `${level} ${dimension}`,
    };
  }

  function titleCase(value) {
    return String(value)
      .split(/[\s_-]+/)
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  function markdownBlocks(markdown) {
    const lines = markdown.split(/\r?\n/);
    const blocks = [];
    let paragraph = [];
    let list = null;

    const flushParagraph = () => {
      if (!paragraph.length) {
        return;
      }
      blocks.push(el("p", "", cleanInline(paragraph.join(" "))));
      paragraph = [];
    };

    const flushList = () => {
      if (!list) {
        return;
      }
      blocks.push(list);
      list = null;
    };

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        flushParagraph();
        flushList();
        continue;
      }
      if (trimmed.startsWith("## ")) {
        flushParagraph();
        flushList();
        blocks.push(el("h2", "", cleanInline(trimmed.slice(3))));
        continue;
      }
      if (trimmed.startsWith("# ")) {
        flushParagraph();
        flushList();
        blocks.push(el("h1", "", cleanInline(trimmed.slice(2))));
        continue;
      }
      if (trimmed.startsWith("* ")) {
        flushParagraph();
        if (!list) {
          list = el("ul");
        }
        list.appendChild(el("li", "", cleanInline(trimmed.slice(2))));
        continue;
      }
      paragraph.push(trimmed);
    }

    flushParagraph();
    flushList();
    return blocks;
  }

  function cleanInline(text) {
    return text
      .replace(/\*\*/g, "")
      .replace(/\*/g, "")
      .replace(/ {2,}/g, " ")
      .trim();
  }

  function el(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }
})();
