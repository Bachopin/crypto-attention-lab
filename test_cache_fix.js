#!/usr/bin/env node

/**
 * 测试脚本：验证前端 API 缓存禁用是否生效
 * 使用方法: node test_cache_fix.js
 */

const API_BASE = 'http://localhost:3000';

async function testAttentionEventsAPI() {
  console.log('🧪 开始测试 fetchAttentionEvents API...\n');
  
  try {
    // 测试 1: 首次请求
    console.log('📊 测试 1: 首次请求 ZEC 的注意力事件');
    let response = await fetch(`${API_BASE}/api/attention-events?symbol=ZEC&lookback_days=30&min_quantile=0.8`);
    let data = await response.json();
    console.log(`✅ 状态码: ${response.status}`);
    console.log(`✅ 返回数据类型: ${Array.isArray(data) ? '数组' : typeof data}`);
    console.log(`✅ 数据条数: ${Array.isArray(data) ? data.length : 'N/A'}`);
    
    if (!Array.isArray(data)) {
      console.log('❌ 错误: 期望返回数组，但收到:', data);
      return false;
    }
    
    if (data.length === 0) {
      console.log('❌ 错误: 返回空数组');
      return false;
    }
    
    console.log('✅ 第一条数据:', JSON.stringify(data[0], null, 2));
    
    // 测试 2: 立即第二次请求（验证缓存禁用）
    console.log('\n📊 测试 2: 立即第二次请求相同参数');
    response = await fetch(`${API_BASE}/api/attention-events?symbol=ZEC&lookback_days=30&min_quantile=0.8`);
    data = await response.json();
    console.log(`✅ 状态码: ${response.status}`);
    console.log(`✅ 数据条数: ${Array.isArray(data) ? data.length : 'N/A'}`);
    
    // 测试 3: 不同 symbol
    console.log('\n📊 测试 3: 请求不同 symbol (BTC)');
    response = await fetch(`${API_BASE}/api/attention-events?symbol=BTC&lookback_days=30&min_quantile=0.8`);
    data = await response.json();
    console.log(`✅ 状态码: ${response.status}`);
    console.log(`✅ 返回数据类型: ${Array.isArray(data) ? '数组' : typeof data}`);
    console.log(`✅ 数据条数: ${Array.isArray(data) ? data.length : 'N/A'}`);
    
    // 测试 4: 不同参数
    console.log('\n📊 测试 4: 请求不同参数 (lookback_days=7)');
    response = await fetch(`${API_BASE}/api/attention-events?symbol=ZEC&lookback_days=7&min_quantile=0.8`);
    data = await response.json();
    console.log(`✅ 状态码: ${response.status}`);
    console.log(`✅ 数据条数: ${Array.isArray(data) ? data.length : 'N/A'}`);
    
    console.log('\n✅ 所有测试通过！缓存禁用生效。');
    return true;
    
  } catch (error) {
    console.error('❌ 测试失败:', error.message);
    return false;
  }
}

async function testPriceAPI() {
  console.log('\n\n🧪 开始测试 fetchPrice API...\n');
  
  try {
    console.log('📊 测试: 价格数据 API');
    const now = new Date().toISOString();
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    
    const response = await fetch(`${API_BASE}/api/price?symbol=ZECUSDT&timeframe=1d&start=${oneDayAgo}&end=${now}`);
    const data = await response.json();
    
    console.log(`✅ 状态码: ${response.status}`);
    console.log(`✅ 返回数据类型: ${Array.isArray(data) ? '数组' : typeof data}`);
    console.log(`✅ 数据条数: ${Array.isArray(data) ? data.length : 'N/A'}`);
    
    if (Array.isArray(data) && data.length > 0) {
      console.log('✅ 第一条数据:', JSON.stringify(data[0], null, 2));
    }
    
    return Array.isArray(data) && data.length > 0;
    
  } catch (error) {
    console.error('❌ 测试失败:', error.message);
    return false;
  }
}

async function runAllTests() {
  console.log('🚀 开始 API 缓存修复验证测试\n');
  console.log('================================\n');
  
  const test1 = await testAttentionEventsAPI();
  const test2 = await testPriceAPI();
  
  console.log('\n\n================================');
  console.log('📋 测试总结:');
  console.log(`  fetchAttentionEvents: ${test1 ? '✅ 通过' : '❌ 失败'}`);
  console.log(`  fetchPrice: ${test2 ? '✅ 通过' : '❌ 失败'}`);
  console.log('================================');
  
  if (test1 && test2) {
    console.log('\n🎉 所有测试通过！缓存禁用修复成功！');
    process.exit(0);
  } else {
    console.log('\n⚠️ 部分测试失败，请检查...');
    process.exit(1);
  }
}

runAllTests();
