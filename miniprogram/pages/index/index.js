var app = getApp();

Page({
  data: {
    dashboard: null, dLoading: true,
    lastScore: '--', scoreLabel: '', scorePct: 0,
    programPct: 0, programDay: 0,
    greeting: '', insight: null,
    notLoggedIn: false,
    showLoginPrompt: false,
    showEmptyGuide: false,
    // Dream world
    dreamIcon: '🌙', dreamTitle: '梦境海 · 等待记录',
    dreamSub: '记录昨晚的睡眠，开启你的梦境世界',
    dreamBg: 'linear-gradient(135deg, #1a1520, #201825, #1a1520)',
    // Guardian
    guardian: { focus: 0, wisdom: 0, resilience: 0, vitality: 0, ritualStreak: 0, garden: { plants: 0, flowers: 0, trees: 0, watered: false, streak: 0 } },
    // Surprise
    surprise: '',
    // Tip
    dailyTip: '',
    // Goals
    goalTags: [],
    // Stats
    streakDays: 0, avgDuration: 0, weeklyAvg: '--',
    // Progressive unlock
    daysSinceJoin: 0,
  },

  onShow() {
    var that = this;
    this.setData({
      greeting: this.getGreeting(),
      notLoggedIn: !app.globalData.token,
    });
    if (app.globalData.token) {
      this.loadDashboard();
    } else {
      this.setData({ greeting: '🌙 欢迎来到梦眠阁' });
    }
    // Guardian state
    var g = app.globalData.guardian;
    this.setData({ guardian: g, dailyTip: app.getDailyTip() });
    // Goals
    this.setData({ goalTags: app.globalData.priList });
    // Dream scene
    this.updateDreamScene();
    // Surprise
    var s = app.rollSurprise();
    if (s) {
      this.setData({ surprise: s });
      setTimeout(function () { that.setData({ surprise: '' }); }, 5000);
    }
    // Daily reset
    app.dailyReset();
  },

  updateDreamScene() {
    var score = this.data.lastScore;
    if (score === '--') score = null;
    var scene = app.getDreamScene(score);
    this.setData({
      dreamIcon: scene.icon,
      dreamTitle: scene.title,
      dreamSub: scene.sub,
      dreamBg: scene.bg,
    });
  },

  async loadDashboard() {
    try {
      var d = await app.get('/api/v1/wellness/dashboard');
      var score = d.last_sleep ? (d.last_sleep.score || 0) : 0;
      this.setData({
        dashboard: d,
        lastScore: d.last_sleep ? score : '--',
        scorePct: score || 0,
        scoreLabel: score >= 80 ? '优秀' : score >= 60 ? '良好' : score >= 40 ? '一般' : score ? '待改善' : '--',
        programPct: d.program ? d.program.pct : 0,
        programDay: d.program ? d.program.day : 0,
        insight: d.daily_insight || null,
        notLoggedIn: false,
        streakDays: d.streak_days || 0,
        avgDuration: d.avg_duration || 0,
        weeklyAvg: d.weekly_avg ? d.weekly_avg.toFixed(1) + 'h' : '0.0h',
        daysSinceJoin: (d.user && d.user.days_since_join) || 0,
      });
      this.setData({ dLoading: false });
      this.updateDreamScene();
    } catch (e) {
      if (!this.data.dashboard) {
        this.setData({ dLoading: false });
      }
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/login/login' }); },
  dismissSurprise() { this.setData({ surprise: '' }); },

  insightAction() {
    var route = this.data.insight && this.data.insight.action ? this.data.insight.action.route : null;
    if (route) {
      if (route.indexOf('/pages/') === 0) {
        var isTab = route === '/pages/record/record' || route === '/pages/profile/profile';
        if (isTab) wx.switchTab({ url: route });
        else wx.navigateTo({ url: route });
      }
    }
  },

  getGreeting() {
    var h = new Date().getHours();
    if (h < 6) return '夜深了 🌙';
    if (h < 9) return '早上好 ☀️';
    if (h < 12) return '上午好 🌤️';
    if (h < 18) return '下午好 🌈';
    if (h < 22) return '晚上好 🌆';
    return '该休息了 🌙';
  },

  goRecord() { wx.switchTab({ url: '/pages/record/record' }); },
  goChat() { wx.navigateTo({ url: '/pages/chat/chat' }); },
  goTasks() { wx.navigateTo({ url: '/pages/tasks/tasks' }); },
  goGame() { wx.navigateTo({ url: '/pages/game/game' }); },
  goCourses() { wx.navigateTo({ url: '/pages/courses/courses' }); },
  goNoise() { wx.navigateTo({ url: '/pages/noise/noise' }); },
  goProfile() { wx.switchTab({ url: '/pages/profile/profile' }); },
});
