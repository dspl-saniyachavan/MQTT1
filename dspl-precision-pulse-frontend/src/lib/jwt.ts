import { SignJWT, jwtVerify } from 'jose';

function getSecret(): Uint8Array {
  const secret = process.env.JWT_SECRET;
  if (!secret) throw new Error('JWT_SECRET environment variable is not set');
  return new TextEncoder().encode(secret);
}

export async function signToken(payload: any): Promise<string> {
  try {
    return await new SignJWT(payload)
      .setProtectedHeader({ alg: 'HS256' })
      .setIssuedAt()
      .setExpirationTime('24h')
      .sign(getSecret());
  } catch (error) {
    console.error('Token signing failed:', error);
    throw error;
  }
}

export async function verifyToken(token: string) {
  try {
    if (!token) {
      return null;
    }
    const { payload } = await jwtVerify(token, getSecret());
    return payload;
  } catch (error) {
    console.error('Token verification failed:', error);
    return null;
  }
}

export function decodeToken(token: string) {
  try {
    if (!token) return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    
    const decoded = JSON.parse(
      Buffer.from(parts[1], 'base64').toString('utf-8')
    );
    return decoded;
  } catch (error) {
    console.error('Token decode failed:', error);
    return null;
  }
}
