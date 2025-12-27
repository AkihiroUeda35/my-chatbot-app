import axios from 'axios';

// Configure axios defaults - use empty string to leverage Next.js proxy
axios.defaults.baseURL = '';
axios.defaults.headers.common['Content-Type'] = 'application/json';

export default axios;
