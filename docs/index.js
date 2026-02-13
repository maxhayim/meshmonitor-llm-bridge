const version = "v1.0.0";

document.getElementById("install").textContent =
`docker exec -it meshmonitor sh -lc "
wget -O /data/scripts/mm_llm_bridge.py https://raw.githubusercontent.com/maxhayim/meshmonitor-llm-bridge/${version}/mm_llm_bridge.py &&
chmod +x /data/scripts/mm_llm_bridge.py &&
python3 -m py_compile /data/scripts/mm_llm_bridge.py &&
echo OK
"`;
