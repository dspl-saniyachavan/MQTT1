export interface User {
  id: string;
  email: string;
  password: string;
  name: string;
  role: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface UserCreateInput {
  email: string;
  password: string;
  name: string;
  role?: string;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  role: string;
}
