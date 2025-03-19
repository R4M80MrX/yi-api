import axios from 'axios';

// API基础URL
const API_BASE_URL = 'http://localhost:3002/api';

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 获取占卜解读
export const getDivinationInterpretation = async (
  matter: string, 
  hexagram: string, 
  lines: string[]
) => {
  try {
    const response = await api.post('/divination/interpret', {
      matter,
      hexagram,
      lines
    });
    return response.data;
  } catch (error) {
    console.error('获取占卜解读失败:', error);
    throw error;
  }
};

// 添加待办事项
export const addTodoItem = async (
  title: string, 
  description: string, 
  hexagram?: string
) => {
  try {
    const response = await api.post('/todos', {
      title,
      description,
      hexagram,
      completed: false,
      createdAt: new Date().toISOString()
    });
    return response.data;
  } catch (error) {
    console.error('添加待办事项失败:', error);
    throw error;
  }
}; 