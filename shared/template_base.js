/* ═══════════════════════════════════════════════════════════════════════════
   news-stock-selector · 统一 JS 模板 v1.0
   融合: mingli30119/stock-analysis 图表框架 + 双主题切换
   依赖: ECharts (CDN) — 可选，无图表时正常降级
   数据注入: window.__REPORT_DATA__ 全局对象
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  /* ───────────────────────────────────────────────
   * 1. 主题切换
   * ─────────────────────────────────────────────── */
  const STORAGE_KEY = "nss-theme-preference";

  function getSavedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (_) {
      return null;
    }
  }
  function saveTheme(mode) {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch (_) {
      /* noop */
    }
  }

  function applyTheme(mode) {
    if (mode === "light") {
      document.body.classList.add("light-mode");
    } else {
      document.body.classList.remove("light-mode");
    }
    updateToggleButton(mode);
    saveTheme(mode);
  }

  function updateToggleButton(mode) {
    var btn = document.getElementById("themeToggle");
    if (!btn) return;
    btn.textContent = mode === "light" ? "🌙 深色模式" : "☀️ 浅色模式";
  }

  function initTheme() {
    var saved = getSavedTheme();
    if (saved === "light" || saved === "dark") {
      applyTheme(saved);
      return;
    }
    // 无手动偏好时跟随系统
    if (
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: light)").matches
    ) {
      applyTheme("light");
    }
    // 默认深色（不设置 light-mode 类）
  }

  var toggleBtn = document.getElementById("themeToggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      var isLight = document.body.classList.contains("light-mode");
      applyTheme(isLight ? "dark" : "light");
      // 重新渲染所有 ECharts 图表以适配新主题色
      if (typeof echarts !== "undefined") {
        renderAllCharts();
      }
    });
  }

  // 初始化主题
  initTheme();

  /* ───────────────────────────────────────────────
   * 2. 主题色获取（供图表使用）
   * ─────────────────────────────────────────────── */
  function getThemeColors() {
    var style = getComputedStyle(document.body);
    return {
      text: style.getPropertyValue("--text").trim() || "#e2e4e7",
      textSecondary:
        style.getPropertyValue("--text-secondary").trim() || "#8d929a",
      textMuted: style.getPropertyValue("--text-muted").trim() || "#5d626b",
      up: style.getPropertyValue("--up").trim() || "#f85149",
      down: style.getPropertyValue("--down").trim() || "#3fb950",
      gold: style.getPropertyValue("--gold-light").trim() || "#e3c26d",
      goldDim: style.getPropertyValue("--gold").trim() || "#d4a853",
      blue: style.getPropertyValue("--blue").trim() || "#58a6ff",
      orange: style.getPropertyValue("--orange").trim() || "#e8923a",
      bg: style.getPropertyValue("--bg").trim() || "#0a0e14",
      bgCard: style.getPropertyValue("--bg-card").trim() || "#141820",
      border: style.getPropertyValue("--border").trim() || "#262d38",
    };
  }

  /* ───────────────────────────────────────────────
   * 3. 数据注入 & 图表容器检测
   * ─────────────────────────────────────────────── */
  var reportData = window.__REPORT_DATA__ || null;
  var chartInstances = {};

  function hasECharts() {
    return typeof echarts !== "undefined";
  }

  function hasChartContainer(id) {
    return document.getElementById(id) !== null;
  }

  function disposeChart(id) {
    if (chartInstances[id]) {
      chartInstances[id].dispose();
      delete chartInstances[id];
    }
  }

  function initChart(id) {
    disposeChart(id);
    var dom = document.getElementById(id);
    if (!dom) return null;
    var chart = echarts.init(dom);
    chartInstances[id] = chart;
    return chart;
  }

  /* ───────────────────────────────────────────────
   * 4. 图表渲染函数
   * ─────────────────────────────────────────────── */

  // 4a. 板块涨跌柱状图（sector-bar）
  function renderSectorBar() {
    var id = "chart-sector-bar";
    if (!hasChartContainer(id)) return;
    var chart = initChart(id);
    if (!chart) return;
    var c = getThemeColors();
    var sectors = (reportData && reportData.sectors) || [];
    if (!sectors.length) {
      chart.dispose();
      return;
    }

    chart.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: {
        left: "3%",
        right: "8%",
        top: "6%",
        bottom: "6%",
        containLabel: true,
      },
      xAxis: {
        type: "value",
        axisLabel: { color: c.textMuted, fontSize: 10, formatter: "{value}%" },
        splitLine: { lineStyle: { color: c.border } },
      },
      yAxis: {
        type: "category",
        data: sectors.map(function (s) {
          return s.name;
        }),
        axisLabel: { color: c.textSecondary, fontSize: 11 },
        axisLine: { lineStyle: { color: c.border } },
      },
      series: [
        {
          type: "bar",
          data: sectors.map(function (s) {
            return {
              value: s.chg,
              itemStyle: { color: s.chg >= 0 ? c.up : c.down },
            };
          }),
          barWidth: "60%",
          label: {
            show: true,
            position: "right",
            fontSize: 10,
            color: c.textSecondary,
            formatter: function (p) {
              return (p.value >= 0 ? "+" : "") + p.value.toFixed(2) + "%";
            },
          },
        },
      ],
    });
  }

  // 4b. 单股 K 线迷你图（per-stock: chart-kline-{code}）
  function renderStockKline(code) {
    var id = "chart-kline-" + code;
    if (!hasChartContainer(id)) return;
    var chart = initChart(id);
    if (!chart) return;
    var c = getThemeColors();

    var stocks = (reportData && reportData.stocks) || [];
    var stock = null;
    for (var i = 0; i < stocks.length; i++) {
      if (stocks[i].code === code) {
        stock = stocks[i];
        break;
      }
    }
    if (!stock || !stock.kline_data || !stock.kline_data.length) {
      chart.dispose();
      return;
    }

    var raw = stock.kline_data; // [[date, open, high, low, close, vol], ...]
    var dates = [],
      ohlc = [],
      vols = [],
      closes = [];
    raw.forEach(function (d) {
      dates.push(d[0]);
      ohlc.push([d[1], d[4], d[3], d[2]]); // [open, close, low, high]
      vols.push(+(d[5] / 10000).toFixed(2));
      closes.push(d[4]);
    });
    var dateLabels = dates.map(function (d) {
      var parts = d.split("-");
      return parts[1] + "-" + parts[2];
    });
    var ma5 = calcMA(closes, 5);
    var volData = vols.map(function (v, i) {
      return {
        value: v,
        itemStyle: {
          color:
            ohlc[i][1] >= ohlc[i][0]
              ? "rgba(248,81,73,0.35)"
              : "rgba(63,185,80,0.35)",
        },
      };
    });

    chart.setOption({
      grid: [
        { left: "10%", right: "4%", top: "10%", height: "50%" },
        { left: "10%", right: "4%", top: "70%", height: "16%" },
      ],
      xAxis: [
        {
          type: "category",
          data: dateLabels,
          gridIndex: 0,
          axisLabel: {
            color: c.textMuted,
            fontSize: 9,
            interval: Math.max(1, Math.floor(dateLabels.length / 6)),
          },
          axisLine: { lineStyle: { color: c.textMuted } },
        },
        { type: "category", data: dateLabels, gridIndex: 1, show: false },
      ],
      yAxis: [
        {
          scale: true,
          gridIndex: 0,
          axisLabel: { color: c.textMuted, fontSize: 10 },
          splitLine: { show: false },
        },
        {
          scale: true,
          gridIndex: 1,
          axisLabel: {
            color: c.textMuted,
            fontSize: 10,
            formatter: "{value}万",
          },
          splitLine: { show: false },
        },
      ],
      dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }],
      tooltip: { trigger: "axis" },
      series: [
        {
          name: "K线",
          type: "candlestick",
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          itemStyle: {
            color: c.up,
            color0: c.down,
            borderColor: c.up,
            borderColor0: c.down,
          },
        },
        {
          name: "MA5",
          type: "line",
          data: ma5,
          smooth: true,
          lineStyle: { width: 1.5, color: c.gold },
          showSymbol: false,
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: "成交量",
          type: "bar",
          data: volData,
          xAxisIndex: 1,
          yAxisIndex: 1,
        },
      ],
    });
  }

  // 4c. 市场情绪饼图
  function renderSentimentPie() {
    var id = "chart-sentiment-pie";
    if (!hasChartContainer(id)) return;
    var chart = initChart(id);
    if (!chart) return;
    var c = getThemeColors();
    var sentiment = (reportData && reportData.sentiment) || null;
    if (!sentiment) {
      chart.dispose();
      return;
    }

    chart.setOption({
      tooltip: { trigger: "item", formatter: "{b}: {c} 只 ({d}%)" },
      series: [
        {
          type: "pie",
          radius: ["45%", "72%"],
          data: [
            {
              value: sentiment.t1_count || 0,
              name: "T1·强烈看好",
              itemStyle: { color: "#f85149" },
            },
            {
              value: sentiment.t2_count || 0,
              name: "T2·看好",
              itemStyle: { color: "#58a6ff" },
            },
            {
              value: sentiment.t3_count || 0,
              name: "T3·关注",
              itemStyle: { color: "#8d929a" },
            },
          ],
          label: { fontSize: 11, color: c.textSecondary },
        },
      ],
    });
  }

  /* ───────────────────────────────────────────────
   * 5. 指标计算工具
   * ─────────────────────────────────────────────── */
  function calcMA(arr, n) {
    return arr.map(function (_, i) {
      if (i < n - 1) return null;
      var sum = 0;
      for (var j = i - n + 1; j <= i; j++) sum += arr[j];
      return +(sum / n).toFixed(2);
    });
  }

  /* ───────────────────────────────────────────────
   * 6. 全部图表渲染入口
   * ─────────────────────────────────────────────── */
  function renderAllCharts() {
    if (!hasECharts()) return;

    // 板块涨跌柱状图
    renderSectorBar();

    // 市场情绪饼图
    renderSentimentPie();

    // 各股票迷你 K 线
    var stocks = (reportData && reportData.stocks) || [];
    stocks.forEach(function (s) {
      if (s.kline_data && s.kline_data.length) {
        renderStockKline(s.code);
      }
    });
  }

  /* ───────────────────────────────────────────────
   * 7. 导航滚动高亮
   * ─────────────────────────────────────────────── */
  function initNavScroll() {
    var navLinks = document.querySelectorAll(".nav-links a");
    if (!navLinks.length) return;

    var sections = document.querySelectorAll("[data-nav-section]");
    if (!sections.length) return;

    window.addEventListener("scroll", function () {
      var cur = "";
      sections.forEach(function (s) {
        if (window.scrollY >= s.offsetTop - 120) {
          cur = s.getAttribute("data-nav-section");
        }
      });
      navLinks.forEach(function (a) {
        a.classList.remove("active");
        if (a.getAttribute("href") === "#" + cur) a.classList.add("active");
      });
    });

    navLinks.forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var target = document.querySelector(this.getAttribute("href"));
        if (!target) {
          // fallback: find by data-nav-section
          var sectionId = this.getAttribute("href").replace("#", "");
          target = document.querySelector(
            '[data-nav-section="' + sectionId + '"]',
          );
        }
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  /* ───────────────────────────────────────────────
   * 8. 响应式图表 Resize
   * ─────────────────────────────────────────────── */
  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      Object.keys(chartInstances).forEach(function (id) {
        try {
          chartInstances[id].resize();
        } catch (_) {
          /* ignore */
        }
      });
    }, 150);
  });

  /* ───────────────────────────────────────────────
   * 9. 初始化
   * ─────────────────────────────────────────────── */
  function init() {
    initNavScroll();

    if (hasECharts()) {
      // 延迟渲染确保 DOM 就绪
      setTimeout(renderAllCharts, 100);
    }
  }

  // DOM 就绪后执行
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  /* ───────────────────────────────────────────────
   * 10. 暴露 API（供外部调用）
   * ─────────────────────────────────────────────── */
  window.__NSS_REPORT__ = {
    renderAllCharts: renderAllCharts,
    getThemeColors: getThemeColors,
    applyTheme: applyTheme,
    getCurrentTheme: function () {
      return document.body.classList.contains("light-mode") ? "light" : "dark";
    },
  };

  /* ───────────────────────────────────────────────
   * 11. v5.1: 投资流派切换 — 完整重排序+重分层
   * ─────────────────────────────────────────────── */
  var SCHOOL_LABELS = {"event":"事件驱动","value":"价值投资","growth":"成长投资","short_term":"短线交易","technical":"技术分析","quant":"量化交易","macro":"宏观投资","speculative":"投机派"};
  var ALL_SCHOOLS = ["event","value","growth","short_term","technical","quant","macro","speculative"];

  function getStrategyClass(strategy) {
    if (!strategy) return "tag-catalyst";
    if (strategy.indexOf("回调") >= 0) return "tag-pullback";
    if (strategy.indexOf("突破") >= 0) return "tag-breakout";
    if (strategy.indexOf("趋势") >= 0) return "tag-momentum";
    return "tag-catalyst";
  }

  /* v5.3: 提取流派应用逻辑为独立函数, 页面加载时自动应用默认流派 */
  function applySchoolTierData(school) {
    var tabs = document.querySelectorAll(".school-tab");
    var t1Card = document.querySelector('[data-nav-section="tier1"]');
    var t2Card = document.querySelector('[data-nav-section="tier2"]');
    var t3Card = document.querySelector('[data-nav-section="tier3"]');
    if (!t1Card || !t2Card || !t3Card) return;
    var t1Body = t1Card.querySelector(".stock-table tbody");
    var t2Body = t2Card.querySelector(".stock-table tbody");
    var t3Body = t3Card.querySelector(".stock-table tbody");
    if (!t1Body || !t2Body || !t3Body) return;

    // 收集所有数据行
    var allRows = [];
    [t1Body, t2Body, t3Body].forEach(function (body) {
      var rows = body.querySelectorAll("tr[data-school-scores]");
      rows.forEach(function (row) { allRows.push(row); });
    });
    if (!allRows.length) return;

    // 为每行分配新 tier 并更新显示
    var newT1 = [], newT2 = [], newT3 = [];
    allRows.forEach(function (row) {
      var scoresStr = row.getAttribute("data-school-scores");
      if (!scoresStr) return;
      try {
        var scores = JSON.parse(scoresStr);
        var sd = scores[school] || scores["event"] || {tier: 3, score: 0, strategy: ""};
        var newTier = sd.tier || 3;
        var newScore = typeof sd.score === "number" ? sd.score.toFixed(3) : String(sd.score || "0.000");
        var newStrategy = sd.strategy || "";

        row.setAttribute("data-tier", String(newTier));
        row.style.display = "";

        var scoreCell = row.querySelector(".score");
        if (scoreCell) scoreCell.textContent = newScore;

        var tagCell = row.querySelector(".tag");
        if (tagCell && newStrategy) {
          tagCell.textContent = newStrategy;
          tagCell.className = "tag " + getStrategyClass(newStrategy);
        }

        if (newTier === 1) newT1.push(row);
        else if (newTier === 2) newT2.push(row);
        else newT3.push(row);
      } catch (e) {}
    });

    // 按分数降序排列各组
    function sortByScore(rows) {
      rows.sort(function (a, b) {
        var sa = parseFloat((a.querySelector(".score") || {}).textContent) || 0;
        var sb = parseFloat((b.querySelector(".score") || {}).textContent) || 0;
        return sb - sa;
      });
    }
    sortByScore(newT1);
    sortByScore(newT2);
    sortByScore(newT3);

    function fillBody(body, rows, emptyMsg) {
      body.innerHTML = "";
      if (rows.length === 0) {
        body.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--text-muted);padding:20px;">' + emptyMsg + '</td></tr>';
        return;
      }
      rows.forEach(function (r) { body.appendChild(r); });
    }
    fillBody(t1Body, newT1, "该流派视角下暂无 T1 标的");
    fillBody(t2Body, newT2, "该流派视角下暂无 T2 标的");
    fillBody(t3Body, newT3, "该流派视角下暂无 T3 标的");

    updateKpiCards(newT1.length, newT2.length, newT3.length, school);
    updateLimitUpWarning(school);
  }

  function initSchoolFilter() {
    var tabs = document.querySelectorAll(".school-tab");
    if (!tabs.length) return;

    // v5.3: 页面加载时自动应用默认激活的流派
    var activeTab = document.querySelector(".school-tab.active");
    if (activeTab) {
      var defaultSchool = activeTab.getAttribute("data-school");
      if (defaultSchool) {
        applySchoolTierData(defaultSchool);
      }
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var school = this.getAttribute("data-school");
        if (!school) return;

        // 更新 tab 激活状态
        tabs.forEach(function (t) { t.classList.remove("active"); });
        this.classList.add("active");

        applySchoolTierData(school);
      });
    });
  }

  function updateKpiCards(t1c, t2c, t3c, school) {
    var kpiCards = document.querySelectorAll(".kpi-value");
    if (kpiCards.length >= 5) {
      kpiCards[0].textContent = t1c;
      kpiCards[1].textContent = t2c;
      kpiCards[2].textContent = t3c;
    }
    // 更新流派标签
    var schoolLabel = SCHOOL_LABELS[school] || school;
    var schoolFilterTitle = document.querySelector("#school-filter .section-title span:last-child");
    if (schoolFilterTitle) {
      schoolFilterTitle.textContent = "当前视角：" + schoolLabel;
    }
  }

  function updateLimitUpWarning(school) {
    // 更新涨停次日提醒中的标的列表（按选中流派）
    var t3Body = document.querySelector('[data-nav-section="tier3"] .stock-table tbody');
    if (!t3Body) return;
    var warnBox = document.querySelector("#tier3-warn-box");
    if (!warnBox) return;
    var limitUpRows = t3Body.querySelectorAll("tr[data-school-scores]");
    var limitUpCodes = [];
    limitUpRows.forEach(function (row) {
      try {
        var scores = JSON.parse(row.getAttribute("data-school-scores") || "{}");
        var sd = scores[school] || scores["event"] || {};
        var code = (row.querySelector(".code") || {}).textContent || "";
        if (sd.tier === 3 && code) limitUpCodes.push(code);
      } catch (e) {}
    });
    if (limitUpCodes.length > 0) {
      warnBox.style.display = "";
      var body = warnBox.querySelector(".warn-body");
      if (body) body.textContent = limitUpCodes.length + "只标的在该流派视角下归入T3，追高风险较大，建议等待回调确认后再考虑介入。";
    } else {
      warnBox.style.display = "none";
    }
  }

  // 初始化
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSchoolFilter);
  } else {
    initSchoolFilter();
  }
})();
