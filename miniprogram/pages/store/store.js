const app = getApp();
Page({
  data: {
    tab: 'products',
    products: [], cart: [], cartTotal: 0, cartCount: 0,
    coupons: [], orders: [],
    viewing: null,
    // Quantity selector
    showQty: null, qtyProduct: null, qty: 1, qtySubtotal: '0.00',
  },
  onShow() {
    this.loadProducts(); this.loadCart(); this.loadCoupons(); this.loadOrders();
  },
  switchTab(e) { this.setData({ tab: e.currentTarget.dataset.tab }); },
  noop() {},

  // Products
  async loadProducts() {
    try { const d = await app.get('/api/v1/store/products'); this.setData({ products: d.products || [] }); } catch {}
  },
  viewProduct(e) {
    const p = this.data.products.find(x => x.id === e.currentTarget.dataset.id);
    this.setData({ viewing: p, showQty: null });
  },
  closeView() { this.setData({ viewing: null, showQty: null }); },
  openQty(e) {
    const product = this.data.viewing || this.data.products.find(p => p.id === e.currentTarget.dataset.id);
    this.setData({ showQty: true, qtyProduct: product, qty: 1, qtySubtotal: product.price_yuan.toFixed(2) });
  },
  addQty() {
    const qty = this.data.qty + 1;
    const subtotal = (this.data.qtyProduct.price_yuan * qty).toFixed(2);
    this.setData({ qty, qtySubtotal: subtotal });
  },
  subQty() {
    if (this.data.qty <= 1) return;
    const qty = this.data.qty - 1;
    const subtotal = (this.data.qtyProduct.price_yuan * qty).toFixed(2);
    this.setData({ qty, qtySubtotal: subtotal });
  },
  async confirmAddToCart() {
    const pid = this.data.qtyProduct.id;
    try {
      await app.post('/api/v1/store/cart', { product_id: pid, quantity: this.data.qty });
      wx.showToast({ title: '已加入购物车', icon: 'success' });
      this.setData({ showQty: null });
      this.loadCart();
    } catch { wx.showToast({ title: '添加失败', icon: 'none' }); }
  },
  async addToCart(e) {
    const pid = e.currentTarget.dataset.id;
    try {
      await app.post('/api/v1/store/cart', { product_id: pid });
      wx.showToast({ title: '已加入购物车', icon: 'success' });
      this.loadCart();
    } catch (e) { wx.showToast({ title: '添加失败', icon: 'none' }); }
  },

  // Cart
  async loadCart() {
    try {
      const d = await app.get('/api/v1/store/cart');
      this.setData({ cart: d.items || [], cartTotal: d.total_yuan || 0, cartCount: (d.items || []).length });
    } catch {}
  },
  async removeFromCart(e) {
    try { await app.del('/api/v1/store/cart/' + e.currentTarget.dataset.id); this.loadCart(); } catch {}
  },
  async createOrder() {
    if (this.data.cartCount === 0) return;
    wx.showModal({
      title: '确认下单',
      content: `合计 ¥${this.data.cartTotal}，确认提交订单？`,
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await app.post('/api/v1/store/orders', { address: '小程序订单' });
          wx.showToast({ title: '下单成功！', icon: 'success' });
          this.loadCart(); this.loadOrders();
        } catch { wx.showToast({ title: '下单失败', icon: 'none' }); }
      },
    });
  },

  // Coupons
  async loadCoupons() {
    try { const d = await app.get('/api/v1/store/coupons'); this.setData({ coupons: d.coupons || [] }); } catch {}
  },
  async claimCoupon(e) {
    try {
      await app.post('/api/v1/store/coupons/claim', { code: e.currentTarget.dataset.code });
      wx.showToast({ title: '领取成功！' });
      this.loadCoupons();
    } catch { wx.showToast({ title: '领取失败', icon: 'none' }); }
  },

  // Orders
  async loadOrders() {
    try { const d = await app.get('/api/v1/store/orders'); this.setData({ orders: d.orders || [] }); } catch {}
  },

  // Helpers
  statusLabel(s) {
    const m = { pending: '待付款', paid: '已付款', shipped: '已发货', completed: '已完成', cancelled: '已取消' };
    return m[s] || s;
  },
});
