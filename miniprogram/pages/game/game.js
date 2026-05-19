var app = getApp();

var DEFAULT_GAMES = [
  { id: 'breathing', name: '呼吸训练', icon: '🫁', attr: 'focus', attrName: '专注力', subtitle: '4-7-8呼吸法', desc: '跟随引导圆环调整呼吸节奏，提升专注力', color: '#3498DB', status: 'active' },
  { id: 'quiz', name: '睡眠问答', icon: '🧩', attr: 'wisdom', attrName: '智慧', subtitle: '知识就是力量', desc: '50道睡眠科学题库等你挑战，提升智慧', color: '#9B59B6', status: 'active' },
  { id: 'worry', name: '烦恼粉碎机', icon: '💥', attr: 'resilience', attrName: '韧性', subtitle: 'CBT-I技术', desc: '写下烦恼然后一个个粉碎，提升韧性', color: '#E74C3C', status: 'active' },
  { id: 'runner', name: '昼夜跑酷', icon: '🏃', attr: 'vitality', attrName: '活力', subtitle: '躲避咖啡因', desc: '左←右→躲避障碍物，提升活力', color: '#E67E22', status: 'active' },
  { id: 'garden', name: '梦境花园', icon: '🌻', attr: '', attrName: '', subtitle: '养成系睡眠', desc: '完成睡眠任务培育专属植物', color: '#2ECC71', status: 'coming' },
  { id: 'adventure', name: '睡眠大冒险', icon: '⚔️', attr: '', attrName: '', subtitle: 'CBT-I RPG', desc: '击败焦虑怪和熬夜龙', color: '#F39C12', status: 'coming' },
  { id: 'soundscape', name: '音景工坊', icon: '🎛️', attr: '', attrName: '', subtitle: '12种自然音效', desc: '自由混音创造专属入睡音景', color: '#1ABC9C', status: 'coming' },
];

var attrNames = { focus: '专注力', wisdom: '智慧', resilience: '韧性', vitality: '活力' };
var attrIcons = { focus: '🧘', wisdom: '📚', resilience: '💪', vitality: '⚡' };

Page({
  data: {
    tab: 'dojo',
    games: DEFAULT_GAMES,
    dashboard: null,
    leaderboard: [],
    achievements: [],
    unlockedCount: 0,
    loggedIn: false,
    guardian: { focus: 0, wisdom: 0, resilience: 0, vitality: 0, ritualStreak: 0 },
    attrRows: [], dotRows: [1, 2, 3, 4], quizLabels: ['A', 'B', 'C', 'D'],
    quizOptLabels: [],
    // Ritual
    ritualMode: '', ritualStep: 0, ritualWorries: [], ritualWorryInput: '',
    ritualBreathDone: false, ritualBreathPhase: '', ritualBreathTimer: 4, ritualBreathRounds: 0, ritualBreathPlaying: false,
    ritualQuizQuestions: [], ritualQuizIdx: 0, ritualQuizScore: 0, ritualQuizDone: false, ritualQuizAnswer: -1,
    ritualQuizCurrent: null, ritualQuizTotal: 0,
    ritualDone: false, ritualXP: 0, ritualFragQuality: 'rare',
    ritualBreathMax: 4,
    breathIv: null
  },

  buildAttrRows: function () {
    var g = this.data.guardian || {};
    var colors = { focus: '#3498DB', wisdom: '#9B59B6', resilience: '#E67E22', vitality: '#E74C3C' };
    var names = { focus: '专注力', wisdom: '智慧', resilience: '韧性', vitality: '活力' };
    var icons = { focus: '🧘', wisdom: '📚', resilience: '💪', vitality: '⚡' };
    var keys = ['focus', 'wisdom', 'resilience', 'vitality'];
    var rows = keys.map(function (k) {
      return { key: k, icon: icons[k], name: names[k], filled: g[k] || 0, color: colors[k] };
    });
    this.setData({ attrRows: rows });
  },

  onShow() {
    var isLogin = !!app.globalData.token;
    this.setData({ loggedIn: isLogin, guardian: app.globalData.guardian });
    this.buildAttrRows();
    if (isLogin) {
      this.loadHall();
    } else {
      this.setData({ games: DEFAULT_GAMES });
    }
  },

  onHide() {
    this.stopRitualBreathing();
  },

  switchTab(e) {
    var tab = e.currentTarget.dataset.tab;
    this.setData({ tab: tab });
    if (!this.data.loggedIn) return;
    if (tab === 'status') this.loadStatus();
    if (tab === 'leaderboard') this.loadLeaderboard();
  },

  // --- Ritual ---
  startRitual() {
    this.setData({
      ritualStep: 0, ritualMode: '', ritualWorries: [], ritualWorryInput: '',
      ritualBreathDone: false, ritualBreathPhase: '', ritualBreathTimer: 4, ritualBreathRounds: 0, ritualBreathPlaying: false,
      ritualQuizQuestions: [], ritualQuizIdx: 0, ritualQuizScore: 0, ritualQuizDone: false, ritualQuizAnswer: -1,
      ritualDone: false, ritualXP: 0, ritualFragQuality: 'rare'
    });
  },

  selectRitualMode(e) {
    var mode = e.currentTarget.dataset.mode;
    var maxRounds = mode === 'quick' ? 2 : mode === 'deep' ? 4 : 4;
    this.setData({ ritualMode: mode, ritualBreathMax: maxRounds, ritualStep: 1, ritualWorries: [], ritualWorryInput: '',
      ritualBreathDone: false, ritualBreathPhase: '', ritualBreathTimer: 4, ritualBreathRounds: 0, ritualBreathPlaying: false,
      ritualQuizQuestions: [], ritualQuizIdx: 0, ritualQuizScore: 0, ritualQuizDone: false, ritualQuizAnswer: -1,
      ritualDone: false, ritualXP: 0, ritualFragQuality: 'rare' });
  },

  onRitualWorryInput: function (e) { this.setData({ ritualWorryInput: e.detail.value }); },
  addRitualWorry() {
    var text = this.data.ritualWorryInput.trim();
    if (!text) return;
    var worries = this.data.ritualWorries;
    worries.unshift({ id: Date.now(), text: text });
    this.setData({ ritualWorries: worries, ritualWorryInput: '' });
  },

  ritualNextStep() {
    var step = this.data.ritualStep;
    if (step === 2 && this.data.ritualMode === 'quick' && this.data.ritualBreathDone) {
      this.finishRitual(); return;
    }
    if (step === 3) this.loadRitualQuiz();
    if (step === 3 && this.data.ritualMode === 'standard' && this.data.ritualQuizDone) {
      this.finishRitual(); return;
    }
    if (step === 4) { this.finishRitual(); return; }
    this.setData({ ritualStep: step + 1, ritualBreathDone: false });
  },

  startRitualBreathing() {
    var that = this;
    var max = this.data.ritualBreathMax;
    var phases = [{ p: '吸气', d: 4 }, { p: '屏息', d: 7 }, { p: '呼气', d: 8 }];
    var round = 0;
    this.setData({ ritualBreathPlaying: true, ritualBreathRounds: 0 });

    function runCycle() {
      if (!that.data.ritualBreathPlaying) return;
      var pi = 0;
      function tick() {
        if (!that.data.ritualBreathPlaying) return;
        if (pi >= phases.length) {
          round++;
          that.setData({ ritualBreathRounds: round });
          if (round >= max) {
            that.setData({ ritualBreathDone: true, ritualBreathPlaying: false });
            app.addAttr('focus', 1);
            return;
          }
          pi = 0;
        }
        var ph = phases[pi];
        that.setData({ ritualBreathPhase: ph.p, ritualBreathTimer: ph.d });
        var t = ph.d;
        var iv = setInterval(function () {
          t--;
          if (t <= 0) { clearInterval(iv); pi++; tick(); }
          else { that.setData({ ritualBreathTimer: t }); }
        }, 1000);
        that.setData({ breathIv: iv });
      }
      tick();
    }
    runCycle();
  },

  stopRitualBreathing() {
    if (this.data.breathIv) clearInterval(this.data.breathIv);
    this.setData({ ritualBreathPlaying: false, ritualBreathPhase: '', ritualBreathTimer: 4, breathIv: null });
  },

  async loadRitualQuiz() {
    try {
      var data = await app.get('/api/v1/game/quiz/questions');
      var questions = (data.questions || []).map(function (q) {
        var labels = ['A', 'B', 'C', 'D'];
        q.opts = (q.opts || []).map(function (opt, i) {
          return { label: labels[i] || '', text: opt };
        });
        return q;
      });
      this.setData({
        ritualQuizQuestions: questions, ritualQuizIdx: 0, ritualQuizScore: 0,
        ritualQuizDone: false, ritualQuizAnswer: -1,
        ritualQuizCurrent: questions.length > 0 ? questions[0] : null,
        ritualQuizTotal: questions.length
      });
    } catch (e) { wx.showToast({ title: '加载题目失败', icon: 'none' }); }
  },

  answerRitualQuiz(e) {
    if (this.data.ritualQuizAnswer >= 0) return;
    var idx = e.currentTarget.dataset.idx;
    var q = this.data.ritualQuizQuestions[this.data.ritualQuizIdx];
    var score = this.data.ritualQuizScore;
    if (idx === q.ans) score += 20;
    this.setData({ ritualQuizAnswer: idx, ritualQuizScore: score });
  },

  nextRitualQuiz() {
    var total = this.data.ritualMode === 'deep' ? 5 : 3;
    var idx = this.data.ritualQuizIdx + 1;
    if (idx >= Math.min(total, this.data.ritualQuizQuestions.length)) {
      this.setData({ ritualQuizDone: true });
      if (this.data.ritualQuizScore >= 40) app.addAttr('wisdom', 1);
      if (this.data.ritualMode === 'standard') {
        var that = this;
        setTimeout(function () { that.finishRitual(); }, 500);
      }
    } else {
      this.setData({
        ritualQuizIdx: idx, ritualQuizAnswer: -1,
        ritualQuizCurrent: this.data.ritualQuizQuestions[idx]
      });
    }
  },

  finishRitual() {
    var qs = ['common', 'common', 'common', 'rare', 'rare', 'epic', 'legendary'];
    var q = qs[Math.min(qs.length - 1, Math.floor(app.globalData.guardian.ritualStreak / 3) + Math.floor(Math.random() * 3))];
    var xp = this.data.ritualMode === 'deep' ? 50 : this.data.ritualMode === 'standard' ? 30 : 15;
    app.addFragment(q);
    app.globalData.guardian.ritualStreak++;
    app.globalData.guardian.lastRitual = app._today();
    app.saveGuardian();
    app.waterGarden();
    this.setData({ ritualDone: true, ritualXP: xp, ritualFragQuality: q, guardian: app.globalData.guardian });
    this.buildAttrRows();
  },

  exitRitual() {
    this.stopRitualBreathing();
    this.setData({ ritualStep: 0, ritualDone: false, ritualMode: '' });
  },

  // --- Existing ---
  async loadHall() {
    try {
      var data = await app.get('/api/v1/game/hall');
      this.setData({ games: data.games || DEFAULT_GAMES });
    } catch (e) { }
  },

  async loadStatus() {
    try {
      var results = await Promise.all([app.get('/api/v1/game/dashboard'), app.get('/api/v1/game/achievements')]);
      var d = results[0];
      var a = results[1];
      var ach = a.achievements || [];
      this.setData({ dashboard: d, achievements: ach, unlockedCount: ach.filter(function (x) { return x.unlocked; }).length });
    } catch (e) { }
  },

  async loadLeaderboard() {
    try {
      var data = await app.get('/api/v1/game/leaderboard');
      var medals = ['🥇', '🥈', '🥉'];
      var list = (data.leaderboard || []).map(function (item) {
        item.medal = item.rank <= 3 ? medals[item.rank - 1] : item.rank;
        return item;
      });
      this.setData({ leaderboard: list });
    } catch (e) { }
  },

  enterGame(e) {
    var id = e.currentTarget.dataset.id;
    var game = this.data.games.find(function (g) { return g.id === id; });
    if (!game) return;
    if (game.status === 'coming') { wx.showToast({ title: '即将上线', icon: 'none' }); return; }
    app.post('/api/v1/game/hall/' + id + '/visit').catch(function () { });
    var gamePages = { 'garden': 'garden', 'adventure': 'adventure', 'breathing': 'breathing', 'worry': 'worry', 'quiz': 'quiz', 'soundscape': 'sound', 'runner': 'runner' };
    var page = gamePages[id];
    if (page) wx.navigateTo({ url: '/pages/game/' + page + '/' + page });
  },

  goLogin() { wx.navigateTo({ url: '/pages/login/login' }); },

  async checkin() {
    if (!this.data.loggedIn) { app._promptLogin(); return; }
    try {
      var data = await app.post('/api/v1/game/checkin');
      wx.showToast({ title: data.message, icon: 'success' });
      this.loadHall();
    } catch (e) { wx.showToast({ title: '今日已签到', icon: 'none' }); }
  },
});
