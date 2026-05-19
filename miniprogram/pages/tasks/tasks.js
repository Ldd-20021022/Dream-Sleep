var app = getApp();

var TIME_LABELS = { morning: '☀️ 晨间仪式', afternoon: '🌤️ 日间习惯', evening: '🌙 睡前准备' };
var TIME_ORDER = ['morning', 'afternoon', 'evening'];

Page({
  data: {
    groups: [],
    badges: [],
    points: 0,
    loading: true,
    streakWeek: [],
    streakCount: 0,
    doneCount: 0,
    totalCount: 0,
    progressPct: 0,
    animTaskId: null,
    animXP: 0,
    showBadgeCelebration: false,
    newBadge: null,
    goalTags: [],
  },

  _calcStats() {
    const groups = this.data.groups;
    let done = 0, total = 0;
    for (const g of groups) {
      for (const t of g.tasks) {
        total++;
        if (t.done) done++;
      }
    }
    const sw = this.data.streakWeek || [];
    let sc = 0;
    for (let i = 0; i < sw.length; i++) { if (sw[i]) sc++; }
    this.setData({
      doneCount: done, totalCount: total,
      progressPct: total > 0 ? Math.round(done / total * 100) : 0,
      streakCount: sc,
    });
  },

  onShow() { this.loadData(); this.setData({ goalTags: app.globalData.priList }); },

  dateKey() {
    const d = new Date();
    return `${d.getFullYear()}-${d.getMonth()+1}-${d.getDate()}`;
  },

  async loadData() {
    this.setData({ loading: true });
    try {
      const [tasksRes, badgesRes, pointsRes, prevBadgeIds] = await Promise.all([
        app.get('/api/v1/tasks/today').catch(() => ({ tasks: [], streak_week: [] })),
        app.get('/api/v1/tasks/badges').catch(() => []),
        app.get('/api/v1/tasks/points/summary').catch(() => ({ total_points: 0 })),
        this._getPrevBadgeIds(),
      ]);

      const tasks = tasksRes.tasks || [];
      const streakWeek = tasksRes.streak_week || [];
      const completions = await app.get(`/api/v1/tasks/${this.dateKey()}`).catch(() => []);
      const compIds = (completions || []).map(c => c.task_id);

      // Group tasks by time_of_day
      const grouped = {};
      for (const t of tasks) {
        const tod = t.time_of_day || 'evening';
        if (!grouped[tod]) grouped[tod] = [];
        t.done = compIds.includes(t.id);
        grouped[tod].push(t);
      }

      const groups = TIME_ORDER
        .filter(k => grouped[k] && grouped[k].length > 0)
        .map(k => ({ key: k, label: TIME_LABELS[k], tasks: grouped[k] }));

      // Check for newly unlocked badges
      const badges = badgesRes || [];
      const currentUnlocked = badges.filter(b => b.unlocked).map(b => b.badge_id);
      const newBadgeId = currentUnlocked.find(id => !prevBadgeIds.includes(id));
      const newBadge = newBadgeId ? badges.find(b => b.badge_id === newBadgeId) : null;

      this.setData({
        groups, badges, points: (pointsRes.total_points || 0), loading: false, streakWeek,
        showBadgeCelebration: !!newBadge, newBadge,
      });
      this._calcStats();

      if (newBadge) this._saveBadgeIds(currentUnlocked);
    } catch { this.setData({ loading: false }); }
  },

  async toggleTask(e) {
    var taskId = e.currentTarget.dataset.id;
    var dk = this.dateKey();
    var groupKey = e.currentTarget.dataset.group;
    var isDone = this._isDone(taskId);

    // Optimistic update: update UI immediately
    this._updateTaskStatus(taskId, groupKey, !isDone);
    if (!isDone) {
      this.setData({ animTaskId: taskId, animXP: 5 });
      setTimeout(function () { this.setData({ animTaskId: null, animXP: 0 }); }.bind(this), 1200);
    }

    try {
      if (isDone) {
        await app.del('/api/v1/tasks/complete', { task_id: taskId, date_key: dk });
      } else {
        await app.post('/api/v1/tasks/complete', { task_id: taskId, date_key: dk });
        var pts = await app.get('/api/v1/tasks/points/summary').catch(function () { return {}; });
        this.setData({ points: pts.total_points || this.data.points + 5 });
        this._refreshStreak();
      }
    } catch (e) {
      // Revert on failure
      this._updateTaskStatus(taskId, groupKey, isDone);
    }
  },

  dismissCelebration() {
    this.setData({ showBadgeCelebration: false, newBadge: null });
  },

  _isDone(taskId) {
    for (const g of this.data.groups) {
      for (const t of g.tasks) {
        if (t.id === taskId) return t.done;
      }
    }
    return false;
  },

  _updateTaskStatus(taskId, groupKey, done) {
    const groups = this.data.groups.map(g => {
      if (g.key !== groupKey) return g;
      return {
        ...g,
        tasks: g.tasks.map(t => t.id === taskId ? { ...t, done } : t),
      };
    });
    this.setData({ groups });
    this._calcStats();
  },

  async _refreshStreak() {
    try {
      const res = await app.get('/api/v1/tasks/today').catch(() => ({}));
      this.setData({ streakWeek: res.streak_week || this.data.streakWeek });
    } catch {}
  },

  _getPrevBadgeIds() {
    try {
      return wx.getStorageSync('prevBadgeIds') || [];
    } catch { return []; }
  },

  _saveBadgeIds(ids) {
    try { wx.setStorageSync('prevBadgeIds', ids); } catch {}
  },
});
