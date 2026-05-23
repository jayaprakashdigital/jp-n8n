#!/bin/bash
# Sets up log rotation for AIOS logs

cat > /etc/logrotate.d/aios << 'EOF'
/root/aios/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

echo "Log rotation configured"
