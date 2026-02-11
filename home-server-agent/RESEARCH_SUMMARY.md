# Reddit Research Summary: Common Home Server Issues

## Research Sources
- r/selfhosted
- r/homelab
- r/HomeServer
- r/docker
- r/Tailscale

## Common Complaints Found (15+ Issues)

### 1. Docker Permission Issues
**Frequency:** Very High  
**Symptoms:** "Cannot connect to Docker daemon", "permission denied while trying to connect", "Got permission denied"

**Root Causes:**
- User not added to docker group
- Docker daemon not running
- Socket permissions incorrect
- New group membership not applied (requires logout/login)

**Fixes Implemented:**
- Pre-flight check: `check_docker_daemon_socket()` - Detects permission issues before installation
- Automatic docker group addition in planner
- Clear error message suggesting `newgrp docker` or logout/login
- Verification step after group change

---

### 2. Port 53 Conflict (systemd-resolved vs AdGuard)
**Frequency:** Very High  
**Symptoms:** "Address already in use", "bind: address already in use", AdGuard fails to start

**Root Causes:**
- systemd-resolved using port 53
- Other DNS services running
- Docker internal DNS on port 53

**Fixes Implemented:**
- Pre-flight check: `check_dns_configuration()` - Detects systemd-resolved
- Planner includes automatic systemd-resolved handling
- Clear documentation in known_issues

---

### 3. Docker Network Conflicts with VPN
**Frequency:** High  
**Symptoms:** VPN stops working after Docker install, can't reach VPN subnets

**Root Causes:**
- Docker default bridge (172.17.0.0/16) conflicts with corporate VPN
- Route conflicts between Docker and VPN

**Fixes Implemented:**
- Pre-flight check: `check_docker_network_conflicts()` - Detects 172.17.x.x usage
- Warning with suggested fix to configure `bip` in daemon.json
- Documentation for custom bridge IP configuration

---

### 4. SSL Certificate Headaches (Let's Encrypt)
**Frequency:** High  
**Symptoms:** "Certificate expired", "ACME challenge failed", "rate limited", "connection refused on port 80"

**Root Causes:**
- Port 80/443 blocked by firewall
- DNS not pointing to server
- Too many failed attempts (rate limiting)
- Router port forwarding not configured

**Fixes Implemented:**
- Pre-flight check: `check_ssl_certificate_capability()` - Verifies Let's Encrypt reachability
- Pre-flight check: `check_port_forwarding_requirement()` - Warns if needed
- Tailscale Funnel as alternative (no port forwarding needed)
- Domain validation before setup
- Rate limiting awareness in documentation

---

### 5. Reverse Proxy Configuration Complexity
**Frequency:** High  
**Symptoms:** "502 Bad Gateway", "Websocket errors", "redirect loops", "mixed content warnings"

**Root Causes:**
- Missing WebSocket support
- Incorrect upstream configuration
- HTTPS/HTTP mismatch
- Header forwarding issues

**Fixes Implemented:**
- Multiple reverse proxy options (Caddy, Nginx, Traefik) with easy config
- Automatic WebSocket header configuration
- HTTPS redirect handling
- Pre-configured templates for each service

---

### 6. Update Breaking Things
**Frequency:** High  
**Symptoms:** "Everything was working, now it's not", containers won't start after update

**Root Causes:**
- Breaking changes in Docker images
- Configuration format changes
- Database migrations failing
- Dependency conflicts

**Fixes Implemented:**
- Pre-flight check: `check_update_policy()` - Warns about update configuration
- Planner includes pinned image versions where possible
- Backup reminders before updates
- Rollback commands in every plan step

---

### 7. Backup/Restore Problems
**Frequency:** High  
**Symptoms:** "Lost all my data", "backup corrupted", "can't restore", "database locked"

**Root Causes:**
- No backup strategy
- Backing up running containers
- Insufficient disk space for backups
- Wrong backup targets (volumes vs bind mounts)

**Fixes Implemented:**
- Pre-flight check: `check_backup_destination()` - Verifies backup space
- Automatic backup path creation
- Documentation for proper backup procedures
- Warning about database consistency

---

### 8. Storage Driver Issues
**Frequency:** Medium  
**Symptoms:** "Slow performance", "out of space" despite disk having room, graph driver errors

**Root Causes:**
- Using deprecated drivers (aufs, devicemapper)
- Not using overlay2
- Root filesystem filling up with Docker layers
- No log rotation

**Fixes Implemented:**
- Pre-flight check: `check_docker_storage_driver()` - Detects non-optimal drivers
- Pre-flight check: `check_log_rotation()` - Ensures Docker log rotation
- Suggests migrating to overlay2
- Documentation for storage cleanup

---

### 9. Memory/Swap Issues
**Frequency:** Medium  
**Symptoms:** "OOM killed", "out of memory", system freezing, containers crashing

**Root Causes:**
- No swap configured
- Insufficient RAM for containers
- Memory limits not set
- Memory leaks in applications

**Fixes Implemented:**
- Pre-flight check: `check_memory_swap()` - Detects missing swap
- Suggests swap file creation
- RAM requirement checks
- Container memory limit recommendations

---

### 10. Firewall Lockout
**Frequency:** Medium  
**Symptoms:** "Can't SSH anymore after enabling UFW", locked out of server

**Root Causes:**
- Enabling UFW without allowing SSH first
- Docker bypassing UFW rules
- iptables rules conflicting

**Fixes Implemented:**
- Pre-flight check: `check_firewall_configuration()` - CRITICAL warning if SSH not allowed
- Security module includes firewall rule generation with SSH first
- Warning about enabling UFW without SSH

---

### 11. Timezone Issues
**Frequency:** Medium  
**Symptoms:** Scheduled tasks running at wrong times, certificate expiry warnings, log timestamps off

**Root Causes:**
- Default UTC timezone not appropriate
- Container timezone not matching host
- Cron jobs scheduled in wrong timezone

**Fixes Implemented:**
- Pre-flight check: `check_timezone_configuration()` - Detects UTC default
- Suggests setting local timezone
- Container timezone mounting recommendations

---

### 12. Kernel/AppArmor/SELinux Issues
**Frequency:** Medium  
**Symptoms:** "Permission denied" inside containers, bind mounts not working, containers fail to start

**Root Causes:**
- AppArmor profiles blocking container operations
- SELinux preventing volume mounts
- Outdated kernel lacking container features

**Fixes Implemented:**
- Pre-flight check: `check_kernel_version()` - Warns on old kernels
- Pre-flight check: `check_apparmor_selinux()` - Detects MAC systems
- Suggests checking AppArmor/SELinux logs
- Documentation for profile creation

---

### 13. Network Filesystem Issues
**Frequency:** Medium  
**Symptoms:** "NFS share slow", "database corruption", "file locking issues"

**Root Causes:**
- Running databases on NFS/CIFS
- Network latency affecting I/O
- File locking not supported

**Fixes Implemented:**
- Pre-flight check: `check_disk_io_performance()` - Detects network filesystems
- Warning about database-on-NFS
- Recommendation for local storage for databases

---

### 14. Tailscale Connectivity Issues
**Frequency:** Medium  
**Symptoms:** "Can't reach server via Tailscale", "DNS not resolving", "Direct connection not working"

**Root Causes:**
- Tailscale not running
- MagicDNS not enabled
- Subnet routes not configured
- Firewall blocking tailscale0 interface

**Fixes Implemented:**
- Security module includes Tailscale funnel configuration
- Pre-flight verification of Tailscale status
- Firewall rules for tailscale0 interface
- Documentation for troubleshooting

---

### 15. Domain/DNS Configuration Failures
**Frequency:** Medium  
**Symptoms:** "Domain not resolving", "certificate for wrong domain", "DNS propagation issues"

**Root Causes:**
- DNS records not configured
- A vs CNAME confusion
- TTL delays
- Wrong domain format entry

**Fixes Implemented:**
- Interview validates domain format with regex
- Clear summary of required DNS records
- Post-install notes with exact DNS configuration needed
- CNAME vs A record documentation

## Summary of Fixes Implemented

### Pre-flight Checks Added (12 new checks):
1. `check_docker_daemon_socket()` - Docker permission issues
2. `check_docker_storage_driver()` - Storage driver optimization
3. `check_docker_network_conflicts()` - VPN conflicts
4. `check_ssl_certificate_capability()` - SSL readiness
5. `check_firewall_configuration()` - SSH lockout prevention
6. `check_port_forwarding_requirement()` - Network requirements
7. `check_backup_destination()` - Backup space verification
8. `check_update_policy()` - Update awareness
9. `check_timezone_configuration()` - Timezone setup
10. `check_log_rotation()` - Log management
11. `check_memory_swap()` - Memory/swap configuration
12. `check_kernel_version()` - Kernel compatibility
13. `check_apparmor_selinux()` - MAC system awareness
14. `check_disk_io_performance()` - Filesystem type check

### Security Module Features:
- Domain validation
- Tailscale Funnel integration
- Authentication middleware setup (Authelia, OAuth, Basic Auth)
- Rate limiting configuration
- Firewall rule generation
- Security audit reporting
- Credential generation and secure storage

### Planner Improvements:
- Automatic reverse proxy configuration (Caddy, Nginx, Traefik)
- Tailscale Funnel integration
- Authentication middleware deployment
- Rate limiting setup
- DNS configuration documentation
- Rollback commands for every step

### Interview Enhancements:
- Comprehensive domain configuration
- Subdomain selection per service
- Reverse proxy selection
- Security options (Tailscale vs External)
- Authentication requirements
- Configuration summary and confirmation

## References

Based on patterns from:
- r/selfhosted "What issues have you faced?" threads
- r/homelab "Lessons learned" posts
- Docker GitHub issues
- Tailscale troubleshooting guides
- Let's Encrypt community forums
