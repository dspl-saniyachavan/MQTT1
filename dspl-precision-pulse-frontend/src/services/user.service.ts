import bcrypt from 'bcryptjs';
import { User, UserResponse } from '@/models/user';

// Mock database - Replace with actual PostgreSQL connection
const users: User[] = [];

export class UserService {
  async findByEmail(email: string): Promise<User | null> {
    return users.find(u => u.email === email) || null;
  }

  async validatePassword(password: string, hashedPassword: string): Promise<boolean> {
    return await bcrypt.compare(password, hashedPassword);
  }

  async createUser(email: string, password: string, name: string, role: string = 'user'): Promise<UserResponse> {
    const hashedPassword = await bcrypt.hash(password, 10);
    const user: User = {
      id: Date.now().toString(),
      email,
      password: hashedPassword,
      name,
      role,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    users.push(user);
    return this.toUserResponse(user);
  }

  toUserResponse(user: User): UserResponse {
    return {
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    };
  }

  async initializeDefaultUsers(): Promise<void> {
    if (users.length === 0) {
      const defaultUsers: User[] = [
        {
          id: '1',
          email: process.env.ADMIN_EMAIL || 'admin@precisionpulse.com',
          password: bcrypt.hashSync(process.env.ADMIN_PASSWORD || 'admin123', 10),
          name: 'Admin User',
          role: 'admin',
          createdAt: new Date(),
          updatedAt: new Date(),
        },
        {
          id: '2',
          email: process.env.USER_EMAIL || 'user@precisionpulse.com',
          password: bcrypt.hashSync(process.env.USER_PASSWORD || 'user123', 10),
          name: 'Regular User',
          role: 'user',
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      ];
      users.push(...defaultUsers);
    }
  }
}
  