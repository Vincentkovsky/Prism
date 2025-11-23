import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

// Simple token management for demo purposes
// In a real app, this would come from a login flow
let authToken = 'user-test'

api.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

export const setAuthToken = (token: string) => {
  authToken = token
}

export const uploadDocument = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export const submitUrl = (url: string) => {
  return api.post('/documents/from-url', { url })
}

export const getDocumentStatus = (documentId: string) => {
  return api.get(`/documents/${documentId}/status`)
}

export const listDocuments = () => {
  return api.get('/documents')
}

export const qaQuery = (documentId: string, question: string, model: string = 'mini') => {
  return api.post('/qa/query', { document_id: documentId, question, model })
}

export const generateAnalysis = (documentId: string) => {
  return api.post('/qa/analysis/generate', { document_id: documentId })
}

export const getAnalysis = (documentId: string) => {
  return api.get(`/qa/analysis/${documentId}`)
}

