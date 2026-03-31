import axios from 'axios'
import { apiBasePath } from '../utils/base-path'

const client = axios.create({
  baseURL: apiBasePath,
  timeout: 30000,
})

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export default client
