# 凭据与提交校验

新克隆完成后，在首次提交前运行下列命令安装检查。

```sh
brew install gitleaks
python3 scripts/install_git_hooks.py
```

pre-commit 检查 Git 暂存区，pre-push 检查本次推送的每个目标提交及其完整祖先历史。工具缺失或扫描失败会阻止操作。GitHub Secret scan 工作流在 push 和 pull_request 时重新扫描所有可达历史，输出会脱敏。Gitleaks 扩展默认规则，并增加 56 位十六进制 Tushare Token 检测。仅对四个已核实的任务、处理器标识符提供完整值例外，不使用历史泄漏基线或整目录豁免，行内 gitleaks:allow 注释不生效。

凭据通过被忽略的 .env、运行环境或密钥管理服务提供。示例使用占位符，报告和日志也应脱敏。不要把运行容器的完整环境、请求头或 Token 写入审计产物。定期运行 `python3 scripts/check_secrets.py --all` 复核完整历史。

## 凭据泄漏处置

1. 在服务提供方撤销或轮换已泄漏凭据，更新本地 .env 和部署环境。
2. 在隔离克隆中改写所有受影响分支及标签，核验后以明确的旧引用租约推送。
3. 重新克隆并扫描完整历史，检查旧提交的公开缓存。GitHub 的旧 SHA、缓存或其他克隆需要分别处理。
4. 安装提交检查。历史已改写后，协作者应重新克隆或迁移自己的未提交修改，避免合并旧历史。

本仓库已启用 GitHub Secret scanning 和 Push protection。它们的服务端规则覆盖范围由 GitHub 决定。Git 本地钩子可被手工绕过，因此仍需 CI 复扫和凭据轮换。

[GitHub 敏感数据清理说明](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
