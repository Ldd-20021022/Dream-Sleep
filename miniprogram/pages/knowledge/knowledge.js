const app = getApp();

Page({
  data: {
    categories: [],
    activeCat: null,
    articles: [],
    viewingArticle: null,
  },

  onShow() { this.loadCategories(); },

  async loadCategories() {
    try {
      const data = await app.get('/api/v1/wellness/knowledge/categories', false);
      this.setData({ categories: data.categories || [] });
      this.loadArticles();
    } catch {}
  },

  async loadArticles() {
    try {
      const cat = this.data.activeCat;
      const path = '/api/v1/wellness/knowledge/articles' + (cat ? `?category=${encodeURIComponent(cat)}` : '');
      const data = await app.get(path, false);
      this.setData({ articles: data.articles || [] });
    } catch {}
  },

  selectCat(e) {
    this.setData({ activeCat: e.currentTarget.dataset.cat, viewingArticle: null });
    this.loadArticles();
  },

  viewArticle(e) {
    const id = e.currentTarget.dataset.id;
    const article = this.data.articles.find(a => a.id === id);
    this.setData({ viewingArticle: article || null });
  },

  backToList() { this.setData({ viewingArticle: null }); },
});
