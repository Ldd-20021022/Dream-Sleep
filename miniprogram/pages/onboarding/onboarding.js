var app = getApp();

var STEPS = [
  { key: 'basics', title: '基本信息', subtitle: '让我们认识一下你', icon: '👋' },
  { key: 'goal', title: '睡眠目标', subtitle: '你理想中的睡眠是怎样的？', icon: '🎯' },
  { key: 'issues', title: '睡眠困扰', subtitle: '你目前面临哪些问题？', icon: '🔍' },
  { key: 'habits', title: '生活习惯', subtitle: '了解你的日常节奏', icon: '🌿' },
  { key: 'priority', title: '改善目标', subtitle: '你最想改变什么？', icon: '✨' },
];

Page({
  onLoad: function () { this._buildLabels(); },
  data: {
    step: 0, steps: STEPS, submitting: false, errMsg: '',
    age: '', gender: '',
    sleepGoalHours: 8, bedtimeTarget: '22:30', wakeupTarget: '07:00',
    sleepIssues: [], sleepIssueDuration: '',
    issueOptions: ['入睡困难', '夜间醒来', '早醒', '睡眠浅', '多梦', '打鼾', '白天嗜睡', '作息不规律'],
    caffeineIntake: '', exerciseFrequency: '', stressLevel: '',
    improvementPriority: [], primaryGoal: '',
    issuesOpen: false, priorsOpen: false,
    issuesLabel: '点击选择（必选）', priorsLabel: '点击选择（必选）',
    issueOptionsRich: [], priorityOptionsRich: [],
    priorityOptions: ['入睡速度', '睡眠深度', '减少夜醒', '作息规律', '精力恢复', '减少焦虑'],
  },

  nextStep: function () {
    this.setData({ errMsg: '' });
    var s = this.data.step;
    if (s === 0) {
      if (!this.data.age || this.data.age < 12 || this.data.age > 100) { this.setData({ errMsg: '请输入有效的年龄（12-100岁）' }); return; }
      if (!this.data.gender) { this.setData({ errMsg: '请选择性别' }); return; }
    }
    if (s === 1) {
      if (!this.data.sleepGoalHours || this.data.sleepGoalHours < 4) { this.setData({ errMsg: '请设置目标睡眠时长' }); return; }
      if (!this.data.bedtimeTarget) { this.setData({ errMsg: '请设置目标入睡时间' }); return; }
      if (!this.data.wakeupTarget) { this.setData({ errMsg: '请设置目标起床时间' }); return; }
    }
    if (s === 2) {
      if (this.data.sleepIssues.length === 0) { this.setData({ errMsg: '请至少选择一个睡眠问题' }); return; }
      if (!this.data.sleepIssueDuration) { this.setData({ errMsg: '请选择问题持续多久' }); return; }
    }
    if (s === 3) {
      if (!this.data.caffeineIntake) { this.setData({ errMsg: '请选择咖啡因摄入习惯' }); return; }
      if (!this.data.exerciseFrequency) { this.setData({ errMsg: '请选择运动频率' }); return; }
      if (!this.data.stressLevel) { this.setData({ errMsg: '请选择压力水平' }); return; }
    }
    if (s === 4) {
      if (this.data.improvementPriority.length === 0) { this.setData({ errMsg: '请至少选择一个改善方向' }); return; }
      if (!this.data.primaryGoal || !this.data.primaryGoal.trim()) { this.setData({ errMsg: '请填写你的主要目标' }); return; }
      this.finish(); return;
    }
    this.setData({ step: s + 1 });
  },

  prevStep: function () {
    if (this.data.step > 0) this.setData({ step: this.data.step - 1, errMsg: '' });
  },
  toggleIssuesOpen: function () { this.setData({ issuesOpen: !this.data.issuesOpen }); },
  togglePriorsOpen: function () { this.setData({ priorsOpen: !this.data.priorsOpen }); },

  // Step 1
  setAge: function (e) { this.setData({ age: e.detail.value }); },
  setGender: function (e) { this.setData({ gender: e.currentTarget.dataset.v }); },

  // Step 2
  setGoalHours: function (e) { this.setData({ sleepGoalHours: Number(e.detail.value) }); },
  setBedtime: function (e) { this.setData({ bedtimeTarget: e.detail.value }); },
  setWakeup: function (e) { this.setData({ wakeupTarget: e.detail.value }); },

  // Step 3
  _buildLabels: function () {
    var issues = this.data.sleepIssues;
    var priors = this.data.improvementPriority;
    var icons = { '入睡速度': '⚡', '睡眠深度': '💤', '减少夜醒': '🌙', '作息规律': '📅', '精力恢复': '⚡', '减少焦虑': '🧘' };
    this.setData({
      issuesLabel: issues.length > 0 ? '已选 ' + issues.length + ' 项：' + issues.join('、') : '点击选择（必选，至少1项）',
      priorsLabel: priors.length > 0 ? '已选 ' + priors.length + ' 项：' + priors.join('、') : '点击选择（必选，至少1项）',
      issueOptionsRich: this.data.issueOptions.map(function (v) { return { name: v, checked: issues.indexOf(v) > -1 }; }),
      priorityOptionsRich: this.data.priorityOptions.map(function (v) { return { name: v, checked: priors.indexOf(v) > -1, icon: icons[v] || '' }; })
    });
  },

  toggleIssue: function (e) {
    var v = e.currentTarget.dataset.v;
    var arr = this.data.sleepIssues.slice();
    var idx = arr.indexOf(v);
    if (idx > -1) arr.splice(idx, 1); else arr.push(v);
    this.setData({ sleepIssues: arr });
    this._buildLabels();
  },
  setIssueDuration: function (e) { this.setData({ sleepIssueDuration: e.currentTarget.dataset.v }); },

  // Step 4
  setCaffeine: function (e) { this.setData({ caffeineIntake: e.currentTarget.dataset.v }); },
  setExercise: function (e) { this.setData({ exerciseFrequency: e.currentTarget.dataset.v }); },
  setStress: function (e) { this.setData({ stressLevel: e.currentTarget.dataset.v }); },

  // Step 5
  togglePriority: function (e) {
    var v = e.currentTarget.dataset.v;
    var arr = this.data.improvementPriority.slice();
    var idx = arr.indexOf(v);
    if (idx > -1) arr.splice(idx, 1); else if (arr.length < 3) arr.push(v);
    this.setData({ improvementPriority: arr });
    this._buildLabels();
  },
  setPrimaryGoal: function (e) { this.setData({ primaryGoal: e.detail.value }); },

  // Finish
  finish: function () {
    if (this.data.submitting) return;
    this.setData({ submitting: true, errMsg: '' });
    var that = this;
    app.post('/api/v1/wellness/onboarding/complete', {
      age: this.data.age,
      gender: this.data.gender,
      sleep_goal_hours: this.data.sleepGoalHours,
      bedtime_target: this.data.bedtimeTarget,
      wakeup_target: this.data.wakeupTarget,
      sleep_issues: this.data.sleepIssues.join('、'),
      sleep_issue_duration: this.data.sleepIssueDuration,
      caffeine_intake: this.data.caffeineIntake,
      exercise_frequency: this.data.exerciseFrequency,
      stress_level: this.data.stressLevel,
      improvement_priority: this.data.improvementPriority.join(','),
      primary_goal: this.data.primaryGoal,
    }).then(function () {
      app.globalData.priList = that.data.improvementPriority;
      wx.setStorageSync('priList', that.data.improvementPriority);
      wx.showToast({ title: '设置完成！', icon: 'success' });
      setTimeout(function () { wx.switchTab({ url: '/pages/index/index' }); }, 800);
    }).catch(function () {
      wx.showToast({ title: '保存失败，请重试', icon: 'none' });
    }).finally(function () {
      that.setData({ submitting: false });
    });
  },
});
