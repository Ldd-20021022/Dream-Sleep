const app = getApp();
Page({
  data: {
    categories: [], activeCat: null,
    articles: [], bookmarkedIds: [], readHistory: [],
    relatedArticles: [],
    viewingArticle: null, searchQuery: '', isSearching: false,
  },
  onShow() { this.loadCategories(); this.loadBookmarks(); this.loadReadHistory(); },
  async loadCategories() {
    try {
      const data = await app.get('/api/v1/wellness/knowledge/categories', false);
      this.setData({ categories: data.categories || [] });
      if (!this.data.isSearching) this.loadArticles();
    } catch {}
  },
  async loadArticles() {
    try {
      const cat = this.data.activeCat;
      const path = '/api/v1/wellness/knowledge/articles' + (cat ? '?category=' + encodeURIComponent(cat) : '');
      const data = await app.get(path, false);
      this.setData({ articles: data.articles || [] });
    } catch {}
  },
  async loadBookmarks() {
    try {
      const d = await app.get('/api/v1/wellness/knowledge/bookmarks');
      this.setData({ bookmarkedIds: (d.articles || []).map(a => a.id) });
    } catch {}
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
    try {
      const d = await app.get('/api/v1/wellness/knowledge/search?q=' + encodeURIComponent(q), false);
      this.setData({ articles: d.articles || [] });
    } catch {}
  },
  async loadReadHistory() {
    try {
      const d = await app.get('/api/v1/wellness/knowledge/reading-history');
      this.setData({ readHistory: d.articles || [] });
    } catch {}
  },
  viewArticle(e) {
    const id = e.currentTarget.dataset.id;
    const article = this.data.articles.find(a => a.id === id);
    this.setData({ viewingArticle: article || null });
    if (article) {
      // Load related articles and mark as read
      this.loadRelated(article.id);
      app.post('/api/v1/wellness/knowledge/' + article.id + '/read').catch(() => {});
    }
  },
  async loadRelated(articleId) {
    try {
      const d = await app.get('/api/v1/wellness/knowledge/related/' + articleId, false);
      this.setData({ relatedArticles: d.articles || [] });
    } catch {}
  },
  backToList() { this.setData({ viewingArticle: null }); },
  async toggleBookmark(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const res = await app.post('/api/v1/wellness/knowledge/' + id + '/bookmark');
      if (res.bookmarked) {
        this.setData({ bookmarkedIds: [...this.data.bookmarkedIds, id] });
      } else {
        this.setData({ bookmarkedIds: this.data.bookmarkedIds.filter(bid => bid !== id) });
      }
      wx.showToast({ title: res.message, icon: 'none' });
    } catch {}
  },
  isBookmarked(id) { return this.data.bookmarkedIds.includes(id); },
});
