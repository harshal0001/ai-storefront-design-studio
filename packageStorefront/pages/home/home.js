import {
  getStoreInfo,
  collectCouponByUuid,
  searchCouponList,
  getCouponDetail
} from '/api';
import { hideLoading, showLoading } from '/common/loadingOptimization';
const app = getApp();
Page({
  data: {
    loading: true,
    pageError: {
      show: false,
      image: '',
      messages: [],
    },
    storeInfo: {},
    infoCollapsed: true,
    closedCollapsed: true,
    businessHourList: [],
    // message ad
    adList: [
      {
        uuid: '123',
        text: 'Hey there! So glad you’re here, welcome to my amazing store.',
      }
    ],
    couponSwiperActiveIndex: 0,
    productsList: [],
    productsSwiperActiveIndex: 0,
  },
  createConsentDrawerRef(ref) {
    this.consentDrawerRef = ref;
  },
  /**
   * @params {object} options
   * @param {string} shopUuid
   */
  onLoad(options) {
    this.hideAndThenShow = false;
    this.requestLoading = false;
    this.shopUuid = options.shopUuid;
    app.globalData.shopUuid = options.shopUuid;
    my.setNavigationBar({
      title: '',
    });
    this.setData({
      loading: true,
    });
    this.getStoreInfo(() => {
      app.logInfo({
        uuid: this.shopUuid,
        type: 'basic',
      });
    });
  },
  onShow() {
    if (this.hideAndThenShow) {
      this.hideAndThenShow = false;
      this.setData({
        loading: true,
      });
      this.getStoreInfo();
    }
  },
  onHide() {
    this.hideAndThenShow = true;
  },
  getStoreInfo(successCallback) {
    getStoreInfo({
      uuid: this.shopUuid,
      type: 'BASIC',
    }).then((response) => {
      if (response.code === 0) {
        const storeInfo = response.content;
        successCallback && successCallback();
        this.handlePublishedStoreInfo(storeInfo);
      } else if (response.code === 100102) {
        this.setData({
          pageError: {
            show: true,
            image: '/assets/images/page_error_not_found.png',
            messages: ['The merchant is not online yet.', 'Please try again later.'],
          },
          loading: false,
        });
        my.setNavigationBar({
          title: 'Merchant Not Found',
        });
      } else {
        throw new Error(response.message);
      }
    }).catch((err) => {
      this.setData({
        pageError: {
          show: true,
          image: '/assets/images/page_error_unconnected.png',
          messages: ["Looks like there's a little technical issue on our end.", 'Please give it a moment and try again later!'],
        },
        loading: false,
      });
      my.setNavigationBar({
        title: 'Connection Error',
      });
      console.log('getStoreInfo', err, err.message);
    });
  },
  handlePublishedStoreInfo(storeInfo) {
    this.setData({
      storeInfo,
      productsList: this.backProductsList(storeInfo.products),
      businessHourList: this.backBusinessHourList(storeInfo.storefrontInfo.businessInfo.businessHour),
      loading: false,
    });
  },
  backProductsList(products) {
    const productTotal = products.length;
    if (productTotal === 0) {
      return [];
    }
    let productsListCount = Math.floor(productTotal / 2);
    if (productsListCount === 0) {
      return [products];
    }
    const productsList = [];
    const existenceOfRemainder = productTotal % 2;
    if (existenceOfRemainder !== 0) {
      ++productsListCount;
    }
    for (let i = 0; i < productsListCount; i++) {
      productsList[i] = products.slice(i * 2, (i + 1) * 2);
    }
    return productsList;
  },
  backBusinessHourList(businessHour) {
    const foundIndex = businessHour.findIndex((item) => item.dayOfWeek === 'MONDAY');
    if (foundIndex === 0) {
      return [businessHour];
    }
    return [businessHour.slice(0, foundIndex), businessHour.slice(foundIndex)];
  },
  switchInfoCpplapsed() {
    const infoCollapsed = !this.data.infoCollapsed;
    const data = {
      infoCollapsed,
    };
    if (infoCollapsed) {
      data.closedCollapsed = true;
    }
    this.setData(data);
  },
  callPhone() {
    const { contactAreaCode, contactPhone } = this.data.storeInfo.storefrontInfo;
    my.makePhoneCall({
      number: contactAreaCode.slice(1) + contactPhone,
    });
  },
  copyEmail() {
    const email = this.data.storeInfo.storefrontInfo.email;
    my.setClipboard({
      text: email,
      success() {
        my.showToast({
          content: `${email} copied`,
        });
      },
      fail() {
        my.showToast({
          content: 'Copy failed',
        });
      },
    });
  },
  copyAddress() {
    const { localAddress, address } = this.data.storeInfo.storefrontInfo;
    const text = localAddress || address;
    my.setClipboard({
      text,
      success() {
        my.showToast({
          content: `${text}-copied`,
        });
      },
      fail() {
        my.showToast({
          content: 'Copy failed',
        });
      },
    });
  },
  switchClosedCollapsed() {
    this.setData({
      closedCollapsed: !this.data.closedCollapsed,
    });
  },
  openConsentDrawer() {
    const storeInfo = this.data.storeInfo;
    this.consentDrawerRef.initData({
      exclusiveDealsFlag: storeInfo.exclusiveDealsFlag,
      quickAccessFlag: storeInfo.quickAccessFlag,
      shopLevel: storeInfo.shopLevel,
      shopUuid: this.shopUuid,
      localShopName: storeInfo.localShopName,
      shopName: storeInfo.shopName,
    }, true);
  },
  handleConsentDrawerClose(hasChanged, consentStatus) {
    this.consentDrawerRef.closeDrawer();
    if (hasChanged) {
      this.setData({
        storeInfo: {
          ...this.data.storeInfo,
          ...consentStatus,
        }
      });
    }
  },
  handleCouponContainer(coupon) {
    this.handleUseCoupon(coupon);
  },
  hanldeCouponAction(type, coupon) {
    if (type === 'get') {
      this.collectCoupon(coupon);
    } else if (type === 'use') {
      this.handleUseCoupon(coupon);
    }
  },
  collectCoupon(coupon) {
    if (this.requestLoading) {
      return;
    }
    showLoading();
    this.requestLoading = true;
    collectCouponByUuid({
      couponUuid: coupon.couponUuid,
    }).then(({ code, message }) => {
      if (code === 0) {
        my.showToast({
          content: 'Get successfully',
        });
        this.refreshCouponList(coupon.couponUuid);
        return;
      }
      my.showToast({
        content: code === 100207 ? 'Offers are out of inventory' : 'Status changed',
      });
      throw new Error(message);
    }).catch((err) => {
      this.refreshCouponList(coupon.couponUuid);
      console.log('collectCouponByUuiderr', err);
    });
  },
  handleUseCoupon(coupon) {
    if (this.requestLoading) {
      return;
    }
    showLoading();
    this.requestLoading = true;
    const params = {
      couponUuid: coupon.couponUuid,
    };
    if (coupon.userCouponUuid) {
      params.userCouponUuid = coupon.userCouponUuid;
    }
    getCouponDetail(params)
      .then(({ code, message }) => {
        if (code === 0) {
          hideLoading();
          this.requestLoading = false;
          my.navigateTo({
            url: `/packageStorefront/pages/couponDetail/couponDetail?shopUuid=${this.shopUuid}&uuid=${coupon.couponUuid}&userCouponUuid=${coupon.userCouponUuid || ''}`
          });
          return;
        }
        my.showToast({
          content: code === 100207 ? 'Offers are out of inventory' : 'Status changed',
        });
        throw new Error(message);
      }).catch((err) => {
        this.refreshCouponList(coupon.couponUuid);
        console.log('getCouponDetail', err);
      })
  },
  refreshCouponList(couponUuid) {
    searchCouponList({
      uuid: this.shopUuid,
      type: 'basic',
    }).then((response) => {
      if (response.code === 0) {
        const coupons = response.content;
        const foundIndex = coupons.findIndex((item) => item.couponUuid === couponUuid);
        this.setData({
          couponSwiperActiveIndex: foundIndex === -1 ? 0 : foundIndex,
          ['storeInfo.coupons']: coupons,
        });
        hideLoading();
        this.requestLoading = false;
      } else {
        throw new Error(response.message);
      }
    }).catch((err) => {
      hideLoading();
      this.requestLoading = false;
      console.log('searchCouponListerr', err);
    })
  },
  onCouponSwiperChange(e) {
    this.setData({
      couponSwiperActiveIndex: e.detail.current,
    });
  },
  onProductsSwiperChange(e) {
    this.setData({
      productsSwiperActiveIndex: e.detail.current,
    });
  }
});
