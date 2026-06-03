var app = getApp();
Page({
  data: {
    period: 30, trends: null, lastRecord: null, activeTab: 'overview',
    canvasReady: false,
  },
  onShow() { this.loadTrends(); this.loadLastRecord(); },
  async loadLastRecord() {
    try {
      const r = await app.get('/api/v1/sleep-records/last');
      if (r) this.setData({ lastRecord: r });
    } catch {}
  },
  async loadTrends() {
    try {
      const d = await app.get('/api/v1/sleep-records/trends/full?days=' + this.data.period);
      this.setData({ trends: d });
      if (d && d.has_data && this.data.activeTab === 'daily') {
        setTimeout(() => this.drawChart(), 300);
      }
    } catch {}
  },
  changePeriod(e) {
    this.setData({ period: parseInt(e.currentTarget.dataset.days) });
    this.loadTrends();
  },
  setTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ activeTab: tab });
    if (tab === 'daily' && this.data.trends && this.data.trends.has_data) {
      setTimeout(() => this.drawChart(), 300);
    }
  },

  drawChart() {
    const records = this.data.trends.daily || [];
    if (records.length === 0) return;

    const query = wx.createSelectorQuery();
    query.select('#trendCanvas').fields({ node: true, size: true }).exec((res) => {
      if (!res[0] || !res[0].node) return;
      const canvas = res[0].node;
      const ctx = canvas.getContext('2d');
      const dpr = wx.getSystemInfoSync().pixelRatio;
      const w = res[0].width;
      const h = res[0].height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.scale(dpr, dpr);

      const padding = { top: 20, right: 16, bottom: 40, left: 32 };
      const chartW = w - padding.left - padding.right;
      const chartH = h - padding.top - padding.bottom;
      const maxScore = Math.max(...records.map(r => r.score || 0), 10);
      const barW = Math.max(4, Math.min(16, (chartW / records.length) - 4));
      const gap = (chartW - barW * records.length) / (records.length + 1);

      // Grid lines
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 0.5;
      for (let s = 0; s <= 100; s += 20) {
        const y = padding.top + chartH - (s / maxScore) * chartH;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(w - padding.right, y);
        ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '10px sans-serif';
        ctx.fillText(s, 2, y + 3);
      }

      // Bars
      records.forEach((r, i) => {
        const x = padding.left + gap + i * (barW + gap);
        const barH = r.score > 0 ? Math.max(2, (r.score / maxScore) * chartH) : 2;
        const y = padding.top + chartH - barH;
        const color = r.score >= 80 ? '#2ECC71' : r.score >= 60 ? '#3498DB' : r.score >= 40 ? '#F39C12' : '#E74C3C';
        ctx.fillStyle = color;
        ctx.fillRect(x, y, barW, barH);

        // Date label (every 5th)
        if (i % Math.ceil(records.length / 7) === 0) {
          ctx.fillStyle = 'rgba(255,255,255,0.4)';
          ctx.font = '10px sans-serif';
          ctx.fillText((r.date || '').slice(5), x - 8, h - 8);
        }
      });

      this.setData({ canvasReady: true });
    });
  },

  barColor(score) {
    return score >= 80 ? '#2ECC71' : score >= 60 ? '#3498DB' : score >= 40 ? '#F39C12' : '#E74C3C';
  },
  goReport() { wx.navigateTo({ url: '/pages/report/report' }); },
});
