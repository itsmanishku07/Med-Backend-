import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter


class LogAnalyzer:
    """Analyze application logs and generate statistics"""
    
    def __init__(self, log_file_path=None):
        self.log_file_path = log_file_path or os.getenv('LOG_FILE_PATH', 'logs/app.log')
    
    def parse_log_line(self, line):
        """Parse a single log line"""
        try:
            # Extract timestamp
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if not timestamp_match:
                return None
            
            timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
            
            # Extract log level
            level_match = re.search(r' - (DEBUG|INFO|WARNING|ERROR|CRITICAL) - ', line)
            level = level_match.group(1) if level_match else 'UNKNOWN'
            
            # Extract JSON data if present - look for REQUEST, RESPONSE, ERROR, INFO, WARNING
            json_match = re.search(r'(REQUEST|RESPONSE|ERROR|INFO|WARNING): ({.+})', line)
            data = None
            log_type = None
            
            if json_match:
                log_type = json_match.group(1)
                try:
                    json_str = json_match.group(2)
                    # Handle truncated JSON by finding the last complete brace
                    brace_count = 0
                    last_valid_pos = 0
                    for i, char in enumerate(json_str):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                last_valid_pos = i + 1
                                break
                    
                    if last_valid_pos > 0:
                        json_str = json_str[:last_valid_pos]
                    
                    # Python logging uses single quotes, but JSON requires double quotes
                    json_str = json_str.replace("'", '"')
                    
                    data = json.loads(json_str)
                except Exception as e:
                    # If JSON parsing fails, try to extract key info manually
                    pass
            
            return {
                'timestamp': timestamp,
                'level': level,
                'type': log_type,
                'data': data,
                'raw': line.strip()
            }
        except Exception as e:
            return None
    
    def read_logs(self, hours=24, max_lines=10000):
        """Read and parse log files"""
        if not os.path.exists(self.log_file_path):
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        logs = []
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Split by timestamp pattern to get complete log entries
            log_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
            parts = re.split(log_pattern, content)
            
            # Reconstruct log lines
            lines = []
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    # Combine timestamp with its content, remove newlines within the entry
                    log_line = parts[i] + parts[i + 1].replace('\n', ' ').replace('\r', ' ')
                    lines.append(log_line)
            
            # Parse from the end for recent logs
            for line in reversed(lines[-max_lines:]):
                parsed = self.parse_log_line(line)
                if parsed and parsed['timestamp'] >= cutoff_time:
                    logs.append(parsed)
                elif parsed and parsed['timestamp'] < cutoff_time:
                    break
            
            return list(reversed(logs))
        except Exception as e:
            print(f"Error reading logs: {e}")
            import traceback
            traceback.print_exc()
            return []

    
    def get_statistics(self, hours=24):
        """Generate statistics from logs"""
        logs = self.read_logs(hours=hours)
        
        stats = {
            'total_requests': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'avg_response_time': 0,
            'requests_by_hour': defaultdict(int),
            'requests_by_endpoint': Counter(),
            'errors_by_type': Counter(),
            'status_codes': Counter(),
            'top_users': Counter(),
            'slow_requests': [],
            'recent_errors': []
        }
        
        response_times = []
        
        for log in logs:
            if not log['data']:
                continue
            
            # Count requests
            if log['type'] == 'REQUEST':
                stats['total_requests'] += 1
                hour = log['timestamp'].strftime('%Y-%m-%d %H:00')
                stats['requests_by_hour'][hour] += 1
                
                path = log['data'].get('path', 'unknown')
                stats['requests_by_endpoint'][path] += 1
                
                user_id = log['data'].get('user_id')
                if user_id:
                    stats['top_users'][user_id] += 1
            
            # Count responses and response times
            elif log['type'] == 'RESPONSE':
                status_code = log['data'].get('status_code')
                if status_code:
                    stats['status_codes'][str(status_code)] += 1
                
                duration = log['data'].get('duration_ms', 0)
                response_times.append(duration)
                
                # Track slow requests (>2 seconds)
                if duration > 2000:
                    stats['slow_requests'].append({
                        'path': log['data'].get('path'),
                        'duration_ms': duration,
                        'timestamp': log['timestamp'].isoformat()
                    })
            
            # Count errors
            elif log['type'] == 'ERROR':
                stats['total_errors'] += 1
                error_type = log['data'].get('error_type', 'Unknown')
                stats['errors_by_type'][error_type] += 1
                
                stats['recent_errors'].append({
                    'error': log['data'].get('error'),
                    'error_type': error_type,
                    'path': log['data'].get('path'),
                    'timestamp': log['timestamp'].isoformat()
                })
            
            # Count warnings
            elif log['level'] == 'WARNING':
                stats['total_warnings'] += 1
        
        # Calculate average response time
        if response_times:
            stats['avg_response_time'] = round(sum(response_times) / len(response_times), 2)
        
        # Convert defaultdict and Counter to regular dict for JSON serialization
        stats['requests_by_hour'] = dict(stats['requests_by_hour'])
        stats['requests_by_endpoint'] = dict(stats['requests_by_endpoint'].most_common(10))
        stats['errors_by_type'] = dict(stats['errors_by_type'].most_common(10))
        stats['status_codes'] = dict(stats['status_codes'])
        stats['top_users'] = dict(stats['top_users'].most_common(10))
        stats['slow_requests'] = stats['slow_requests'][-20:]  # Last 20 slow requests
        stats['recent_errors'] = stats['recent_errors'][-50:]  # Last 50 errors
        
        return stats
    
    def get_logs_paginated(self, page=1, per_page=100, level=None, search=None, hours=24):
        """Get paginated logs with filtering"""
        logs = self.read_logs(hours=hours)
        
        # Filter by level
        if level:
            logs = [log for log in logs if log['level'] == level.upper()]
        
        # Filter by search term
        if search:
            logs = [log for log in logs if search.lower() in log['raw'].lower()]
        
        # Paginate
        total = len(logs)
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            'logs': logs[start:end],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }
