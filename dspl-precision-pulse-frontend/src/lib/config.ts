export const config = {
  app: {
    name: 'PrecisionPulse',
    version: '1.0.0',
    description: 'Real-time telemetry streaming platform',
  },
  auth: {
    tokenExpiry: '24h',
    saltRounds: 10,
  },
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000',
  },
  mqtt: {
    brokerUrl: process.env.MQTT_BROKER_URL || 'mqtt://localhost:1883',
    username: process.env.MQTT_USERNAME,
    password: process.env.MQTT_PASSWORD,
  },
  database: {
    url: process.env.DATABASE_URL,
  },
};
