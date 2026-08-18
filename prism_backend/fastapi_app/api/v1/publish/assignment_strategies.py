"""
任务分配策略引擎

用于根据不同的分配策略计算视频-账号的任务组合。
分离了"分配策略"(WHAT tasks to create)和"间隔控制"(WHEN tasks execute)。
"""

from typing import List, Dict, Literal, Optional
from dataclasses import dataclass
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class AssignmentConfig:
    """分配策略配置"""
    strategy: Literal["one_per_account", "all_per_account", "cross_platform_all", "per_platform_custom"]
    one_per_account_mode: Optional[Literal["random", "round_robin", "sequential"]] = "random"
    per_platform_overrides: Optional[Dict[int, str]] = None  # {platform_code: strategy}


@dataclass
class TaskAssignment:
    """单个任务分配"""
    file_id: int
    account_id: str
    platform: int
    account_index: int  # 用于间隔计算
    file_index: int     # 用于间隔计算


class AssignmentEngine:
    """任务分配引擎"""

    @staticmethod
    def calculate_tasks(
        file_ids: List[int],
        accounts: List[Dict],
        config: AssignmentConfig
    ) -> List[TaskAssignment]:
        """
        根据策略计算任务分配

        Args:
            file_ids: 文件ID列表
            accounts: 账号列表，每个账号是字典包含 account_id, platform_code 等
            config: 分配策略配置

        Returns:
            任务分配列表
        """
        if not file_ids or not accounts:
            logger.warning("[AssignmentEngine] Empty file_ids or accounts, returning empty task list")
            return []

        logger.info(
            f"[AssignmentEngine] Calculating tasks: "
            f"strategy={config.strategy}, "
            f"files={len(file_ids)}, "
            f"accounts={len(accounts)}"
        )

        if config.strategy == "one_per_account":
            tasks = AssignmentEngine._one_per_account(
                file_ids, accounts, config.one_per_account_mode or "random"
            )
        elif config.strategy == "all_per_account":
            tasks = AssignmentEngine._all_per_account(file_ids, accounts)
        elif config.strategy == "cross_platform_all":
            tasks = AssignmentEngine._cross_platform_all(file_ids, accounts)
        elif config.strategy == "per_platform_custom":
            tasks = AssignmentEngine._per_platform_custom(
                file_ids, accounts, config.per_platform_overrides or {}
            )
        else:
            logger.error(f"[AssignmentEngine] Unknown strategy: {config.strategy}, falling back to all_per_account")
            tasks = AssignmentEngine._all_per_account(file_ids, accounts)

        logger.info(
            f"[AssignmentEngine] Generated {len(tasks)} task assignments "
            f"(strategy={config.strategy}, files={len(file_ids)}, accounts={len(accounts)})"
        )

        return tasks

    @staticmethod
    def _all_per_account(file_ids: List[int], accounts: List[Dict]) -> List[TaskAssignment]:
        """
        策略2: 全覆盖发布
        每个账号发布所有视频 (M × N)
        """
        tasks = []
        for account_idx, account in enumerate(accounts):
            for file_idx, file_id in enumerate(file_ids):
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=account.get('platform_code', 0),
                    account_index=account_idx,
                    file_index=file_idx
                ))

        logger.debug(
            f"[AssignmentEngine.all_per_account] Created {len(tasks)} tasks "
            f"({len(file_ids)} files × {len(accounts)} accounts)"
        )
        return tasks

    @staticmethod
    def _one_per_account(
        file_ids: List[int],
        accounts: List[Dict],
        mode: str = "random"
    ) -> List[TaskAssignment]:
        """
        策略1: 账号单次发布
        每个账号只发布1个视频 (min(M, N))

        Args:
            mode: 分配模式
                - random: 随机分配
                - round_robin: 轮询分配
                - sequential: 顺序分配
        """
        tasks = []
        num_tasks = min(len(file_ids), len(accounts))

        if mode == "random":
            # 随机打乱视频，前N个分配给N个账号
            shuffled_videos = random.sample(file_ids, num_tasks)
            for account_idx, account in enumerate(accounts[:num_tasks]):
                file_id = shuffled_videos[account_idx]
                file_idx = file_ids.index(file_id)
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=account.get('platform_code', 0),
                    account_index=account_idx,
                    file_index=file_idx
                ))
            logger.debug(f"[AssignmentEngine.one_per_account] Random mode: {num_tasks} tasks")

        elif mode == "round_robin":
            # 轮询分配：account_0 → video_0, account_1 → video_1, account_2 → video_0, ...
            for account_idx, account in enumerate(accounts):
                video_idx = account_idx % len(file_ids)
                file_id = file_ids[video_idx]
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=account.get('platform_code', 0),
                    account_index=account_idx,
                    file_index=video_idx
                ))
            logger.debug(f"[AssignmentEngine.one_per_account] Round-robin mode: {len(accounts)} tasks")

        elif mode == "sequential":
            # 顺序分配：account_0 → video_0, account_1 → video_1, ...
            for i in range(num_tasks):
                account = accounts[i]
                file_id = file_ids[i]
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=account.get('platform_code', 0),
                    account_index=i,
                    file_index=i
                ))
            logger.debug(f"[AssignmentEngine.one_per_account] Sequential mode: {num_tasks} tasks")

        else:
            logger.warning(f"[AssignmentEngine.one_per_account] Unknown mode '{mode}', using random")
            return AssignmentEngine._one_per_account(file_ids, accounts, "random")

        return tasks

    @staticmethod
    def _cross_platform_all(file_ids: List[int], accounts: List[Dict]) -> List[TaskAssignment]:
        """
        策略3: 跨平台全覆盖
        每个平台的账号发布所有视频
        """
        # 按平台分组账号
        platform_groups = {}
        for account in accounts:
            platform_code = account.get('platform_code', 0)
            if platform_code not in platform_groups:
                platform_groups[platform_code] = []
            platform_groups[platform_code].append(account)

        tasks = []
        account_idx_global = 0

        for platform_code, platform_accounts in platform_groups.items():
            logger.debug(
                f"[AssignmentEngine.cross_platform_all] "
                f"Platform {platform_code}: {len(platform_accounts)} accounts × {len(file_ids)} files"
            )

            for account_idx_local, account in enumerate(platform_accounts):
                for file_idx, file_id in enumerate(file_ids):
                    tasks.append(TaskAssignment(
                        file_id=file_id,
                        account_id=account['account_id'],
                        platform=platform_code,
                        account_index=account_idx_global,
                        file_index=file_idx
                    ))
                account_idx_global += 1

        logger.debug(
            f"[AssignmentEngine.cross_platform_all] Created {len(tasks)} tasks "
            f"across {len(platform_groups)} platforms"
        )
        return tasks

    @staticmethod
    def _per_platform_custom(
        file_ids: List[int],
        accounts: List[Dict],
        per_platform_overrides: Dict[int, str]
    ) -> List[TaskAssignment]:
        """
        策略4: 平台自定义策略
        为每个平台独立设置分配策略

        Args:
            per_platform_overrides: {platform_code: strategy_name}
        """
        # 按平台分组账号
        platform_groups = {}
        for account in accounts:
            platform_code = account.get('platform_code', 0)
            if platform_code not in platform_groups:
                platform_groups[platform_code] = []
            platform_groups[platform_code].append(account)

        tasks = []
        account_idx_global = 0

        for platform_code, platform_accounts in platform_groups.items():
            # 获取该平台的策略，默认为 all_per_account
            platform_strategy = per_platform_overrides.get(platform_code, "all_per_account")

            logger.debug(
                f"[AssignmentEngine.per_platform_custom] "
                f"Platform {platform_code}: strategy={platform_strategy}, "
                f"accounts={len(platform_accounts)}"
            )

            # 根据平台策略生成任务
            if platform_strategy == "one_per_account":
                platform_tasks = AssignmentEngine._one_per_account_platform_scoped(
                    file_ids, platform_accounts, platform_code, account_idx_global, mode="random"
                )
            elif platform_strategy == "all_per_account":
                platform_tasks = AssignmentEngine._all_per_account_platform_scoped(
                    file_ids, platform_accounts, platform_code, account_idx_global
                )
            else:
                logger.warning(
                    f"[AssignmentEngine.per_platform_custom] "
                    f"Unknown strategy '{platform_strategy}' for platform {platform_code}, "
                    f"using all_per_account"
                )
                platform_tasks = AssignmentEngine._all_per_account_platform_scoped(
                    file_ids, platform_accounts, platform_code, account_idx_global
                )

            tasks.extend(platform_tasks)
            account_idx_global += len(platform_accounts)

        logger.debug(
            f"[AssignmentEngine.per_platform_custom] Created {len(tasks)} tasks "
            f"across {len(platform_groups)} platforms with custom strategies"
        )
        return tasks

    @staticmethod
    def _all_per_account_platform_scoped(
        file_ids: List[int],
        accounts: List[Dict],
        platform_code: int,
        account_idx_start: int
    ) -> List[TaskAssignment]:
        """平台范围内的全覆盖发布"""
        tasks = []
        for account_idx_local, account in enumerate(accounts):
            for file_idx, file_id in enumerate(file_ids):
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=platform_code,
                    account_index=account_idx_start + account_idx_local,
                    file_index=file_idx
                ))
        return tasks

    @staticmethod
    def _one_per_account_platform_scoped(
        file_ids: List[int],
        accounts: List[Dict],
        platform_code: int,
        account_idx_start: int,
        mode: str = "random"
    ) -> List[TaskAssignment]:
        """平台范围内的账号单次发布"""
        tasks = []
        num_tasks = min(len(file_ids), len(accounts))

        if mode == "random":
            shuffled_videos = random.sample(file_ids, num_tasks)
            for account_idx_local, account in enumerate(accounts[:num_tasks]):
                file_id = shuffled_videos[account_idx_local]
                file_idx = file_ids.index(file_id)
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=platform_code,
                    account_index=account_idx_start + account_idx_local,
                    file_index=file_idx
                ))
        else:  # sequential or other
            for i in range(num_tasks):
                account = accounts[i]
                file_id = file_ids[i]
                tasks.append(TaskAssignment(
                    file_id=file_id,
                    account_id=account['account_id'],
                    platform=platform_code,
                    account_index=account_idx_start + i,
                    file_index=i
                ))

        return tasks
