import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios';
import { getCookie, setTokenCookie as setCookieAlias, deleteCookie } from './cookieManager';

const setCookie = (name: string, value: string, _maxAge?: number) => {
  if (name === 'token') setTokenCookieAlias(value);
};
const removeCookie = (name: string) => deleteCookie(name);

function setTokenCookieAlias(token: string) { setCookieAlias(token); }

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
  status?: number;
}

interface ApiError {
  message: string;
  status: number;
  data?: any;
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor - add token to headers
    this.client.interceptors.request.use(
      (config) => {
        const token = getCookie('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle token expiration
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Token expired or invalid
          removeCookie('token');
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  async get<T = any>(url: string, config?: any): Promise<T> {
    try {
      const response = await this.client.get<T>(url, config);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<T> {
    try {
      const response = await this.client.post<T>(url, data, config);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async put<T = any>(url: string, data?: any, config?: any): Promise<T> {
    try {
      const response = await this.client.put<T>(url, data, config);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async patch<T = any>(url: string, data?: any, config?: any): Promise<T> {
    try {
      const response = await this.client.patch<T>(url, data, config);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async delete<T = any>(url: string, config?: any): Promise<T> {
    try {
      const response = await this.client.delete<T>(url, config);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  private handleError(error: any): ApiError {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status || 500;
      const message = error.response?.data?.error || error.message || 'An error occurred';
      return {
        message,
        status,
        data: error.response?.data,
      };
    }
    return {
      message: 'An unexpected error occurred',
      status: 500,
    };
  }

  setToken(token: string) {
    setCookie('token', token, 24 * 60 * 60); // 24 hours
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  clearToken() {
    removeCookie('token');
    delete this.client.defaults.headers.common['Authorization'];
  }
}

export const apiClient = new ApiClient();
