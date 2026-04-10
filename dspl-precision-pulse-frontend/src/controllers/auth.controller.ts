import { UserService } from '@/services/user.service';
import { signToken } from '@/lib/jwt';
import { LoginInput } from '@/schemas/auth.schema';

export class AuthController {
  private userService: UserService;

  constructor() {
    this.userService = new UserService();
  }

  async login(data: LoginInput) {
    const user = await this.userService.findByEmail(data.email);
    
    if (!user) {
      throw new Error('Invalid credentials');
    }

    const isValid = await this.userService.validatePassword(data.password, user.password);
    
    if (!isValid) {
      throw new Error('Invalid credentials');
    }

    const token = await signToken({
      userId: user.id,
      email: user.email,
      role: user.role,
    });

    return {
      token,
      user: this.userService.toUserResponse(user),
    };
  }


}
