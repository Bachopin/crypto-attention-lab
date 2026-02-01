/**
 * PM2 配置文件 - Crypto Attention Lab
 * 
 * 使用方式:
 *   启动本项目:       pm2 start ecosystem.config.cjs
 *   查看状态:         pm2 status
 *   查看日志:         pm2 logs crypto-api / pm2 logs crypto-web
 *   停止本项目:       pm2 stop crypto-api crypto-web
 *   重启本项目:       pm2 restart crypto-api crypto-web
 *   删除本项目:       pm2 delete crypto-api crypto-web
 *   保存开机自启:     pm2 save
 *   
 * 注意: 不要使用 pm2 delete all，会删除其他项目的服务！
 */

const path = require('path');

// 项目根目录
const PROJECT_ROOT = __dirname;

module.exports = {
  apps: [
    {
      // ============ 后端 API ============
      name: 'crypto-api',
      script: './scripts/api.sh',
      cwd: PROJECT_ROOT,
      
      // 环境变量
      env: {
        PYTHONPATH: PROJECT_ROOT,
        NO_PROXY: 'localhost,127.0.0.1,0.0.0.0',
      },
      
      // 进程管理
      instances: 1,
      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 3000,
      
      // 日志配置
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: path.join(PROJECT_ROOT, 'logs/pm2-api-error.log'),
      out_file: path.join(PROJECT_ROOT, 'logs/pm2-api-out.log'),
      merge_logs: true,
      
      // 内存限制（超过自动重启）
      max_memory_restart: '1G',
    },
    
    {
      // ============ 前端 Web ============
      name: 'crypto-web',
      script: 'npm',
      args: 'run start',  // 生产模式，如需开发模式改为 'run dev'
      cwd: path.join(PROJECT_ROOT, 'web'),
      exec_mode: 'fork',  // 使用 fork 模式避免 cluster 警告
      
      // 环境变量
      env: {
        NODE_ENV: 'production',
        PORT: 3000,
        NEXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:8000',
      },
      
      // 开发模式环境变量（用 pm2 start ecosystem.config.cjs --env development）
      env_development: {
        NODE_ENV: 'development',
        PORT: 3000,
        NEXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:8000',
      },
      
      // 进程管理
      instances: 1,
      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 3000,
      
      // 日志配置
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: path.join(PROJECT_ROOT, 'logs/pm2-web-error.log'),
      out_file: path.join(PROJECT_ROOT, 'logs/pm2-web-out.log'),
      merge_logs: true,
      
      // 内存限制
      max_memory_restart: '512M',
    },
  ],
};
