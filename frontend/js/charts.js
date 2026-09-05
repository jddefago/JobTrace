/* Minimal dependency-free chart rendering (plain divs + inline SVG). */

const Icons = {
  send: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`,
  chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>`,
  calendar: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  star: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  doc: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>`,
  trending: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>`,
  trophy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4zM7 4H4a2 2 0 0 0 0 4h1M17 4h3a2 2 0 0 1 0 4h-1"/></svg>`,
  bulb: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 22h4M12 2a6 6 0 0 0-4 10.5c.6.6 1 1.4 1 2.5h6c0-1.1.4-1.9 1-2.5A6 6 0 0 0 12 2z"/></svg>`,
  checkFilled: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  mail: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`,
  gear: `<svg viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" clip-rule="evenodd" d="M11.078 2.25c-.917 0-1.699.663-1.85 1.567L9.05 4.889c-.02.12-.115.26-.297.348a7.493 7.493 0 0 0-.986.57c-.166.115-.334.126-.45.083L6.3 5.508a1.875 1.875 0 0 0-2.282.819l-.922 1.597a1.875 1.875 0 0 0 .432 2.385l.84.692c.095.078.17.229.154.43a7.598 7.598 0 0 0 0 1.139c.015.2-.059.352-.153.43l-.841.692a1.875 1.875 0 0 0-.432 2.385l.922 1.597a1.875 1.875 0 0 0 2.282.818l1.019-.382c.115-.043.283-.031.45.082.312.214.641.405.985.57.182.088.277.228.297.35l.178 1.071c.151.904.933 1.567 1.85 1.567h1.844c.916 0 1.699-.663 1.85-1.567l.178-1.072c.02-.12.114-.26.297-.349.344-.165.673-.356.985-.57.167-.114.335-.125.45-.082l1.02.382a1.875 1.875 0 0 0 2.28-.819l.923-1.597a1.875 1.875 0 0 0-.432-2.385l-.84-.692c-.095-.078-.17-.229-.154-.43a7.614 7.614 0 0 0 0-1.139c-.016-.2.059-.352.153-.43l.84-.692c.708-.582.891-1.59.433-2.385l-.922-1.597a1.875 1.875 0 0 0-2.282-.818l-1.02.382c-.114.043-.282.031-.449-.083a7.49 7.49 0 0 0-.985-.57c-.183-.087-.277-.227-.297-.348l-.179-1.072a1.875 1.875 0 0 0-1.85-1.567h-1.843ZM12 15.75a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5Z"/></svg>`,
  refresh: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.4-6.36L21 8M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.4 6.36L3 16m0 5v-5h5"/></svg>`,
  download: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
  plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>`,
  moon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
};

function iconNode(name, extraClass) {
  return Utils.el("span", { class: `icon-glyph ${extraClass || ""}`, html: Icons[name] || "" });
}

const Charts = (() => {
  function renderDailyBars(container, points) {
    container.innerHTML = "";
    if (!points.length) {
      container.appendChild(Utils.el("div", { class: "empty-state" }, "No applications yet."));
      return;
    }
    const width = Math.max(container.clientWidth || 600, 300);
    const height = 220;
    const padding = { top: 26, right: 10, bottom: 26, left: 10 };
    const innerW = width - padding.left - padding.right;
    const innerH = height - padding.top - padding.bottom;
    const maxCount = Math.max(1, ...points.map((p) => p.count));
    const barGap = points.length > 20 ? 3 : 6;
    const barWidth = Math.max(2, innerW / points.length - barGap);
    const showEvery = Math.max(1, Math.ceil(points.length / 14));

    let svg = `<svg class="chart-daily-bars-svg" viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="none">`;
    for (let g = 0; g <= 3; g++) {
      const y = padding.top + (innerH * g) / 3;
      svg += `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="var(--line-soft)" stroke-width="1" />`;
    }
    points.forEach((p, i) => {
      const barH = maxCount > 0 ? (p.count / maxCount) * innerH : 0;
      const x = padding.left + i * (innerW / points.length);
      const y = padding.top + innerH - barH;
      const cx = x + barWidth / 2;
      svg += `<rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(barH, 1)}" fill="var(--brass)" rx="2"><title>${p.label}: ${p.count}</title></rect>`;
      svg += `<text x="${cx}" y="${y - 7}" font-size="10.5" fill="var(--text-mid)" text-anchor="middle">${p.count}</text>`;
      if (i % showEvery === 0 || i === points.length - 1) {
        svg += `<text x="${cx}" y="${height - 7}" font-size="10" fill="var(--text-low)" text-anchor="middle">${p.label}</text>`;
      }
    });
    svg += `</svg>`;
    container.innerHTML = svg;
  }

  function renderDonut(svgContainer, legendContainer, segments, center) {
    svgContainer.innerHTML = "";
    legendContainer.innerHTML = "";

    const total = segments.reduce((s, seg) => s + Math.max(0, seg.arcValue), 0);
    const size = 200;
    const r = 78;
    const strokeWidth = 26;
    const cx = size / 2;
    const cy = size / 2;
    const circumference = 2 * Math.PI * r;

    let svg = `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">`;
    svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--panel-sunken)" stroke-width="${strokeWidth}" />`;

    let cumulative = 0;
    if (total > 0) {
      for (const seg of segments) {
        const share = Math.max(0, seg.arcValue) / total;
        if (share <= 0) continue;
        const dash = share * circumference;
        const gapDash = circumference - dash;
        const offset = -cumulative * circumference;
        svg += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${seg.color}" stroke-width="${strokeWidth}" stroke-dasharray="${dash} ${gapDash}" stroke-dashoffset="${offset}" transform="rotate(-90 ${cx} ${cy})"><title>${seg.label}: ${seg.count}</title></circle>`;
        cumulative += share;
      }
    }
    svg += `</svg>`;
    svgContainer.innerHTML = svg;

    svgContainer.appendChild(
      Utils.el("div", { class: "donut-center" }, [
        Utils.el("div", { class: "donut-center-label" }, center.label),
        Utils.el("div", { class: "donut-center-value" }, String(center.value)),
        center.sub ? Utils.el("div", { class: "donut-center-sub" }, center.sub) : null,
      ])
    );

    legendContainer.appendChild(
      Utils.el("div", { class: "donut-legend-header" }, [
        Utils.el("span", {}, "Stage"),
        Utils.el("span", {}, "Count"),
        Utils.el("span", {}, "%"),
      ])
    );
    for (const seg of segments) {
      legendContainer.appendChild(
        Utils.el("div", { class: "donut-legend-row" }, [
          Utils.el("div", { class: "donut-legend-label" }, [
            Utils.el("span", { class: "donut-dot", style: `background:${seg.color}` }),
            seg.label,
          ]),
          Utils.el("span", { class: "donut-legend-count" }, String(seg.count)),
          Utils.el("span", { class: "donut-legend-pct" }, Utils.formatPercent(seg.pct)),
        ])
      );
    }
  }

  function renderJourney(container, steps) {
    container.innerHTML = "";

    const track = Utils.el("div", { class: "journey-track" });
    for (let i = 0; i < steps.length - 1; i++) {
      const dashed = !!steps[i + 1].dashedIn;
      const filled = !dashed && steps[i + 1].filled;
      track.appendChild(
        Utils.el("div", { class: `journey-segment ${dashed ? "dashed" : filled ? "filled" : ""}` })
      );
    }

    const nodes = Utils.el("div", { class: "journey-nodes" });
    for (const step of steps) {
      nodes.appendChild(
        Utils.el("div", { class: "journey-node" }, [
          Utils.el(
            "div",
            {
              class: `journey-icon ${step.filled ? "filled" : ""}`,
              style: step.filled ? `border-color:${step.color}; color:${step.color};` : "",
            },
            [iconNode(step.icon)]
          ),
          Utils.el("div", { class: "journey-count" }, String(step.count)),
          Utils.el("div", { class: "journey-label" }, step.label),
          Utils.el("div", { class: "journey-pct" }, Utils.formatPercent(step.pct)),
        ])
      );
    }

    container.appendChild(track);
    container.appendChild(nodes);
  }

  return { renderDailyBars, renderDonut, renderJourney };
})();
