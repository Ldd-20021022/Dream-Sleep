const app = getApp();
Page({
  data: { products: [], cart: [], cartTotal: 0, coupons: [], viewing: null },
  onShow() { this.loadProducts(); this.loadCart(); this.loadCoupons(); },
  async loadProducts() { try { const data = await app.get('/api/v1/store/products'); this.setData({ products: data.products || [] }); } catch {} },
  async loadCart() { try { const data = await app.get('/api/v1/store/cart'); this.setData({ cart: data.items || [], cartTotal: data.total_yuan || 0 }); } catch {} },
  async loadCoupons() { try { const data = await app.get('/api/v1/store/coupons'); this.setData({ coupons: data.coupons || [] }); } catch {} },
  async addToCart(e) { const pid = e.currentTarget.dataset.id; await app.post('/api/v1/store/cart', { product_id: pid }); wx.showToast({ title: '已加入购物车' }); this.loadCart(); },
  async removeFromCart(e) { await app.del('/api/v1/store/cart/' + e.currentTarget.dataset.id); this.loadCart(); },
  async createOrder() { try { await app.post('/api/v1/store/orders', { address: '小程序订单' }); wx.showToast({ title: '下单成功' }); this.loadCart(); } catch { wx.showToast({ title: '下单失败', icon: 'error' }); } },
  viewProduct(e) { const pid = e.currentTarget.dataset.id; this.setData({ viewing: this.data.products.find(p => p.id === pid) }); },
  closeView() { this.setData({ viewing: null }); },
});
