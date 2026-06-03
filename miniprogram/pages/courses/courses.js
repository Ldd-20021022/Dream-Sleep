const app = getApp();
Page({
  data: {
    tab: '21day',
    // 21-day
    program: null, today: null, todayPreview: '', dayList: [],
    progressPct: 0, completedDays: 0, totalDays: 21,
    currentDay: 1, isCompleted: false, started: false, completing: false,
    // Knowledge
    categories: [], activeCat: null, articles: [], bookmarkedIds: [],
    readHistory: [], relatedArticles: [], viewingArticle: null,
    searchQuery: '', isSearching: false,
    // Courses
    courses: [], chapters: [],
    // Shared
    viewing: null, viewingType: '',
    loading: false,
  },
  onShow() {
    if (this.data.tab === '21day') { this.loadProgram(); this.loadProgress(); }
    if (this.data.tab === 'knowledge') { this.loadCategories(); this.loadBookmarks(); }
    if (this.data.tab === 'courses') { this.loadCourses(); }
  },
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ tab, viewing: null, viewingArticle: null });
    if (tab === '21day') { this.loadProgram(); this.loadProgress(); }
    if (tab === 'knowledge' && this.data.categories.length === 0) this.loadCategories();
    if (tab === 'courses' && this.data.courses.length === 0) this.loadCourses();
  },

  // ========== 21-DAY ==========
  async loadProgram() {
    try { const d = await app.get('/api/v1/program/21day'); this.setData({ program: d, totalDays: d.total_days || 21 }); } catch {}
  },
  async loadProgress() {
    try {
      var d = await app.get('/api/v1/program/21day/progress');
      var cur = d.current_day || 1;
      var list = [];
      for (var i = 1; i <= cur; i++) { list.push(i); }
      this.setData({ progressPct: d.progress_pct || 0, currentDay: cur, completedDays: d.completed_days || 0, isCompleted: d.is_completed || false, started: d.started || false, dayList: list });
      if (d.started) this.loadToday();
    } catch (e) {}
  },
  async loadToday() {
    try {
      const d = await app.get('/api/v1/program/21day/today');
      const preview = d.article ? d.article.substring(0, 200) + '...' : '';
      this.setData({ today: d, todayPreview: preview });
    } catch {}
  },
  async startProgram() {
    try { await app.post('/api/v1/program/21day/start'); wx.showToast({ title: '开始21天之旅！', icon: 'success' }); this.loadProgress(); this.loadToday(); } catch {}
  },
  async completeToday() {
    if (this.data.completing) return;
    this.setData({ completing: true });
    try { const d = await app.post('/api/v1/program/21day/complete', {}); wx.showToast({ title: d.message || '完成！', icon: 'success' }); this.loadProgress(); this.loadToday(); } catch (e) { wx.showToast({ title: '请先完成学习', icon: 'none' }); }
    this.setData({ completing: false });
  },
  showLocked: function () {
    wx.showModal({ title: '🔒 课程未解锁', content: '请先完成前面的课程，每天解锁新内容。', showCancel: false, confirmText: '知道了' });
  },
  async viewDay(e) {
    var day = e.currentTarget.dataset.day;
    if (day > this.data.currentDay) { this.showLocked(); return; }
    try { var d = await app.get('/api/v1/program/21day/' + day); this.setData({ viewing: d, viewingType: 'day' }); } catch (e) {}
  },
  closeView() { this.setData({ viewing: null, viewingType: '', viewingArticle: null }); },

  // ========== KNOWLEDGE ==========
  async loadCategories() {
    try {
      const d = await app.get('/api/v1/wellness/knowledge/categories', false);
      this.setData({ categories: d.categories || [] });
      if (!this.data.isSearching) this.loadArticles();
    } catch {}
  },
  async loadArticles() {
    try {
      const cat = this.data.activeCat;
      const path = '/api/v1/wellness/knowledge/articles' + (cat ? '?category=' + encodeURIComponent(cat) : '');
      const d = await app.get(path, false);
      this.setData({ articles: d.articles || [] });
    } catch {}
  },
  async loadBookmarks() {
    try { const d = await app.get('/api/v1/wellness/knowledge/bookmarks'); this.setData({ bookmarkedIds: (d.articles || []).map(a => a.id) }); } catch {}
  },
  selectCat(e) {
    this.setData({ activeCat: e.currentTarget.dataset.cat, viewingArticle: null, searchQuery: '', isSearching: false });
    this.loadArticles();
  },
  onSearchInput(e) { this.setData({ searchQuery: e.detail.value }); },
  async doSearch() {
    const q = this.data.searchQuery.trim();
    if (!q) { this.setData({ isSearching: false }); this.loadArticles(); return; }
    this.setData({ isSearching: true, viewingArticle: null });
    try { const d = await app.get('/api/v1/wellness/knowledge/search?q=' + encodeURIComponent(q), false); this.setData({ articles: d.articles || [] }); } catch {}
  },
  viewArticle(e) {
    const id = e.currentTarget.dataset.id;
    const article = this.data.articles.find(a => a.id === id);
    this.setData({ viewingArticle: article || null });
    if (article) {
      this.loadRelated(article.id);
      app.post('/api/v1/wellness/knowledge/' + article.id + '/read').catch(() => {});
    }
  },
  async loadRelated(articleId) {
    try { const d = await app.get('/api/v1/wellness/knowledge/related/' + articleId, false); this.setData({ relatedArticles: d.articles || [] }); } catch {}
  },
  backToList() { this.setData({ viewingArticle: null }); },
  async toggleBookmark(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await app.post('/api/v1/wellness/knowledge/' + id + '/bookmark');
      if (res.bookmarked) { this.setData({ bookmarkedIds: [...this.data.bookmarkedIds, id] }); }
      else { this.setData({ bookmarkedIds: this.data.bookmarkedIds.filter(bid => bid !== id) }); }
      wx.showToast({ title: res.message, icon: 'none' });
    } catch {}
  },

  // ========== COURSES ==========
  async loadCourses() {
    try { const d = await app.get('/api/v1/courses'); this.setData({ courses: d.courses || [] }); } catch {}
  },
  async viewCourse(e) {
    const id = e.currentTarget.dataset.id;
    const course = this.data.courses.find(c => c.id === id);
    this.setData({ viewing: course, viewingType: 'course' });
    try { const d = await app.get('/api/v1/courses/' + id + '/chapters'); this.setData({ chapters: d.chapters || [] }); } catch {}
  },
  async enrollCourse(e) {
    try { await app.post('/api/v1/courses/' + e.currentTarget.dataset.id + '/enroll'); wx.showToast({ title: '报名成功！' }); } catch {}
  },
});
