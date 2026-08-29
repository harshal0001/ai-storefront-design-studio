import {
  getStoreInfo,
  getCouponDetail,
  getUserCouponBarcode,
  collectCouponByUuid
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
    showPageError: false,
    showAction: false,
    couponDetail: {},
    couponBarcode: '',
  },
  /**
   * @params {object} options
   * @param {string} shopUuid
   * @param {string} uuid coupon uuid
   * @param {string} userCouponUuid if coupon has been fetch, user coupon uuid can set
   */
  onLoad(options) {
    this.shopUuid = options.shopUuid;
    this.couponUuid = options.uuid;
    this.userCouponUuid = options.userCouponUuid;
    app.globalData.shopUuid = options.shopUuid;
    my.setNavigationBar({
      backgroundColor: '#B63F81',
    });
    this.getStoreStatus();
  },
  async getStoreStatus() {
    const response = await getStoreInfo({
      uuid: this.shopUuid,
      type: 'basic',
    });

    if (response.code === 100102) {
      this.setData({
        loading: false,
        pageError: {
          show: true,
          image: '/assets/images/page_error_not_found.png',
          messages: ['The merchant is not online yet.', 'Please try again later.'],
        },
      });
      my.setNavigationBar({
        title: 'Merchant Not Found',
      });
      return;
    }

    this.requestCouponDetail(() => {
      app.logInfo({
        uuid: this.shopUuid,
        type: 'basic',
      });
    });
  },
  async requestCouponDetail(successCallback) {
    this.setData({
      loading: true,
    });
    const params = {
      couponUuid: this.couponUuid,
    };
    if (this.userCouponUuid) {
      params.userCouponUuid = this.userCouponUuid;
    }
    try {
      const couponDetailReponse = await getCouponDetail(params);
      if (couponDetailReponse.code === 0) {
        const couponDetail = couponDetailReponse.content;
        // success callback
        successCallback && successCallback();
        my.setNavigationBar({
          title: couponDetail.name,
        });
        const setData = {
          loading: false,
          couponDetail,
          showAction: couponDetail.viewStatus === 'uncollected'
        };
        if (couponDetail.userCouponCode) {
          this.userCouponUuid = couponDetail.userCouponUuid;
          const couponBarcodeResponse = await getUserCouponBarcode({
            couponUuid: this.couponUuid,
            userCouponUuid: this.userCouponUuid,
          });
          if (couponBarcodeResponse.code === 0) {
            setData.couponBarcode = couponBarcodeResponse.content;
          }
        }
        this.setData(setData);
        return;
      }
      if (typeof couponDetailReponse.code === 'number') {
        this.setData({
          loading: false,
          pageError: {
            show: true,
            image: '/assets/images/page_error_unavailable.png',
            messages: ['The specific item you are looking for', 'is no longer available or may have expired.'],
          },
        });
        my.setNavigationBar({
          title: 'Content Unavailable',
        });
        return;
      }
      if (couponDetailReponse.message) {
        throw new Error(couponDetailReponse.message);
      } else {
        return Promise.reject(couponDetailReponse);
      }
    } catch (err) {
      this.setData({
        loading: false,
        pageError: {
          show: true,
          image: '/assets/images/page_error_unconnected.png',
          messages: ["Looks like there's a little technical issue on our end.", 'Please give it a moment and try again later!'],
        },
      });
      my.setNavigationBar({
        title: 'Connection Error',
      });
      console.log('getCouponDetail', err);
    }
  },
  collectCoupon(type, coupon) {
    showLoading();
    collectCouponByUuid({
      couponUuid: coupon.couponUuid,
    }).then((response) => {
      hideLoading();
      if (response.code === 0) {
        my.showToast({
          content: 'Get successfully',
        });
        this.requestCouponDetail();
      } else {
        this.setData({
          loading: false,
          pageError: {
            show: true,
            image: '/assets/images/page_error_unavailable.png',
            messages: ['The specific item you are looking for', 'is no longer available or may have expired.'],
          },
        });
        my.setNavigationBar({
          title: 'Content Unavailable',
        });
      }
    }).catch((err) => {
      hideLoading();
      my.showToast({
        content: 'Fail to get this offer',
      });
      this.requestCouponDetail();
      console.log('coupon detail collectCouponByUuid', err)
    })
  },
});
