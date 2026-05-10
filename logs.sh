#!/bin/bash
ssh Server@server "/usr/local/bin/docker logs reddit-news-server 2>&1 | tail -300"
