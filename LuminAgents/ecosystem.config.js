module.exports = {
  apps: [
    {
      name: "luminagents-api",
      script: "uvicorn",
      args: "api.main:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      cwd: "/app",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/api-error.log",
      out_file: "logs/api-out.log",
    },
    {
      name: "luminagents-bot",
      script: "python",
      args: "telegram_bot.py",
      interpreter: "none",
      cwd: "/app",
      env: {
        PYTHONUNBUFFERED: "1",
      },
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/bot-error.log",
      out_file: "logs/bot-out.log",
    },
  ],
};
