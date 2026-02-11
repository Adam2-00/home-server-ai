#!/usr/bin/env python3
"""
Maton AI API Client
Uploads files to Google Drive via Maton SaaS integration
"""

import os
import sys
import hashlib
import hmac
import datetime
import requests
from urllib.parse import quote

class MatonClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('MATON_API_KEY')
        if not self.api_key:
            raise ValueError("MATON_API_KEY not set")
        
        self.base_url = "https://api.maton.ai/v1"
        self.region = "us-west-2"  # Discovered from testing
        self.service = "execute-api"
        
    def _sign(self, key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
    
    def _get_signature_key(self, date_stamp):
        k_date = self._sign(("AWS4" + self.api_key).encode('utf-8'), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, self.service)
        k_signing = self._sign(k_service, "aws4_request")
        return k_signing
    
    def _make_request(self, method, path, body=None, params=None):
        t = datetime.datetime.utcnow()
        amz_date = t.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = t.strftime('%Y%m%d')
        
        # Headers
        headers = {
            'host': 'api.maton.ai',
            'x-amz-date': amz_date,
        }
        
        if body:
            headers['content-type'] = 'application/json'
            payload_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
        else:
            payload_hash = hashlib.sha256(''.encode('utf-8')).hexdigest()
        
        headers['x-amz-content-sha256'] = payload_hash
        
        # Try simple Bearer auth first (some APIs accept this)
        headers['Authorization'] = f'Bearer {self.api_key}'
        
        url = f"{self.base_url}{path}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=body, params=params, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, data=body, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            return response
        except Exception as e:
            print(f"Request error: {e}")
            return None
    
    def list_integrations(self):
        """List available integrations (Google Drive, etc.)"""
        response = self._make_request('GET', '/integrations')
        if response:
            print(f"Status: {response.status_code}")
            return response.json()
        return None
    
    def list_tools(self):
        """List available tools"""
        response = self._make_request('GET', '/tools')
        if response:
            print(f"Status: {response.status_code}")
            return response.json()
        return None
    
    def upload_to_drive(self, file_path, folder_id=None):
        """
        Upload file to Google Drive via Maton
        Note: This requires Google Drive to be connected in Maton dashboard
        """
        import mimetypes
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None
        
        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path) or ('application/octet-stream', None)
        
        # Read file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Prepare multipart form data
        files = {
            'file': (file_name, file_content, mime_type)
        }
        
        data = {}
        if folder_id:
            data['folder_id'] = folder_id
        
        # Headers for multipart
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        url = f"{self.base_url}/integrations/google-drive/upload"
        
        try:
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            print(f"Upload status: {response.status_code}")
            return response.json() if response.status_code == 200 else response.text
        except Exception as e:
            print(f"Upload error: {e}")
            return None
    
    def test_connection(self):
        """Test API connection"""
        print(f"Testing Maton API connection...")
        print(f"API Key (first 20 chars): {self.api_key[:20]}...")
        
        # Try to list tools
        result = self.list_tools()
        if result:
            print(f"Response: {result}")
            return True
        return False


def main():
    """Main function"""
    client = MatonClient()
    
    print("=" * 60)
    print("MATON AI API CLIENT")
    print("=" * 60)
    
    # Test connection
    if not client.test_connection():
        print("\n❌ Connection failed")
        print("\nPossible issues:")
        print("1. API key may need to be activated")
        print("2. Google Drive integration may need to be set up in Maton dashboard")
        print("3. Visit https://maton.ai to configure integrations")
        return 1
    
    # List available integrations
    print("\n📋 Available Integrations:")
    integrations = client.list_integrations()
    if integrations:
        print(integrations)
    
    # Upload file if specified
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"\n📤 Uploading {file_path} to Google Drive...")
        result = client.upload_to_drive(file_path)
        if result:
            print(f"✅ Upload result: {result}")
        else:
            print("❌ Upload failed")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
