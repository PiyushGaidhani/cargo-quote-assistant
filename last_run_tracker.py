
import json
import os
from datetime import datetime, timezone, timedelta
import logging

class LastRunTracker:
    def __init__(self, log_file='last_run.json'):
        self.log_file = log_file
        self.last_run_time = self._load_last_run_time()
    
    def _load_last_run_time(self):
        """Load the last run timestamp from file"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    last_run_str = data.get('last_run_time')
                    if last_run_str:
                        return datetime.fromisoformat(last_run_str)
            
            # If no previous run, return 1 hour ago to catch recent emails
            return datetime.now(timezone.utc) - timedelta(hours=1)
            
        except Exception as e:
            logging.error(f"Error loading last run time: {e}")
            return datetime.now(timezone.utc) - timedelta(hours=1)
    
    def update_last_run_time(self):
        """Update the last run time to current time"""
        try:
            current_time = datetime.now(timezone.utc)
            data = {
                'last_run_time': current_time.isoformat(),
                'last_run_human': current_time.strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.last_run_time = current_time
            logging.info(f"Updated last run time to: {current_time}")
            
        except Exception as e:
            logging.error(f"Error updating last run time: {e}")
    
    def get_last_run_time(self):
        """Get the last run time"""
        return self.last_run_time
    
    def should_process_email(self, email_date):
        """Always return True - we'll handle duplicates differently"""
        return True
    
    def get_processed_emails(self):
        """Get list of already processed email IDs"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_emails', []))
            return set()
        except Exception as e:
            logging.error(f"Error loading processed emails: {e}")
            return set()
    
    def mark_email_processed(self, email_id):
        """Mark an email as processed"""
        try:
            # Load existing data
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Add to processed emails set
            processed_emails = set(data.get('processed_emails', []))
            processed_emails.add(email_id)
            data['processed_emails'] = list(processed_emails)
            
            # Keep only last 1000 processed emails to avoid file growing too large
            if len(data['processed_emails']) > 1000:
                data['processed_emails'] = data['processed_emails'][-1000:]
            
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logging.error(f"Error marking email as processed: {e}")
    
    def is_email_processed(self, email_id):
        """Check if email has already been processed"""
        processed_emails = self.get_processed_emails()
        return email_id in processed_emails
