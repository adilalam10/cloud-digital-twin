def recommend(cpu,ram,failed=0):
    if failed: return 'Restore or replace the failed server, then redistribute its workload.'
    if cpu>=85 or ram>=85: return 'High resource pressure: add a virtual server or redistribute workload.'
    if cpu>=70 or ram>=75: return 'Monitor closely; consider scaling out if workload continues to rise.'
    if cpu<25 and ram<35: return 'Resources appear underutilized; consider consolidating workloads.'
    return 'Current allocation looks healthy. Continue monitoring resource trends.'
