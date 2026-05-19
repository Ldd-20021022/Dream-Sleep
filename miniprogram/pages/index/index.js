const app = getApp();

Page({
  data: {
    lastRecord: null,
    stats: {},
    lastDuration: '--',
    lastScore: '--',
    scoreLabel: '',
    dailyTip: '',
  },

  onShow() {
    this.loadData();
    this.setData({
      dailyTip: this.getRandomTip(),
    });
  },

  async loadData() {
    try {
      const [lastRes, statsRes] = await Promise.all([
        app.get('/api/v1/sleep-records/last').catch(() => null),
        app.get('/api/v1/sleep-records/stats/summary?days=7').catch(() => null),
      ]);

      const lastRecord = lastRes || null;
      const stats = statsRes || {};
      const duration = lastRecord ? lastRecord.duration_hours : 0;
      const score = lastRecord ? lastRecord.score : 0;

      this.setData({
        lastRecord,
        stats,
        lastDuration: lastRecord ? `${duration}h` : '--',
        lastScore: lastRecord ? score : '--',
        scoreLabel: score >= 80 ? '优秀' : score >= 60 ? '良好' : score >= 40 ? '一般' : '待改善',
      });
    } catch {}
  },

  getRandomTip() {
    const tips = [
      '保持固定的起床时间，即使是周末也尽量不赖床。',
      '睡前1小时减少屏幕使用，蓝光会抑制褪黑素分泌。',
      '卧室温度保持在18-22°C最有利于入睡。',
      '下午2点后避免摄入咖啡因。',
    ];
    return tips[Math.floor(Math.random() * tips.length)];
  },

  goRecord() { wx.navigateTo({ url: '/pages/record/record' }); },
  goNoise() { wx.navigateTo({ url: '/pages/noise/noise' }); },
  goChat() { wx.navigateTo({ url: '/pages/chat/chat' }); },
  goTasks() { wx.navigateTo({ url: '/pages/tasks/tasks' }); },
});
