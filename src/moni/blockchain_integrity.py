"""
ブロックチェーン統合システム - Moni System Monitor

データ完全性と分散台帳による監視ログの真正性確保を提供します。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class BlockchainTransaction:
    """ブロックチェーントランザクション"""
    tx_id: str
    timestamp: datetime
    data_hash: str
    previous_hash: str
    merkle_root: str
    transaction_type: str  # log_entry, data_verification, system_event, etc.
    data_size: int
    signature: Optional[str] = None
    validator_nodes: List[str] = field(default_factory=list)


@dataclass
class BlockchainBlock:
    """ブロックチェーンブロック"""
    block_id: str
    timestamp: datetime
    previous_block_hash: str
    transactions: List[BlockchainTransaction]
    block_hash: str
    nonce: int
    difficulty: int
    miner_id: str
    block_size: int


@dataclass
class MonitoringLogEntry:
    """監視ログエントリ"""
    log_id: str
    timestamp: datetime
    source: str  # system, application, security, etc.
    level: str  # debug, info, warning, error, critical
    message: str
    data_hash: str
    blockchain_tx_id: Optional[str] = None
    integrity_verified: bool = False


class BlockchainIntegrityManager:
    """ブロックチェーン完全性管理システム"""

    def __init__(self, blockchain_dir: Optional[Union[str, Path]] = None):
        self.blockchain_dir = Path(blockchain_dir) if blockchain_dir else Path(__file__).parent / "blockchain_data"
        self.blockchain_dir.mkdir(exist_ok=True)

        self.blocks: Dict[str, BlockchainBlock] = {}
        self.transactions: Dict[str, BlockchainTransaction] = {}
        self.log_entries: Dict[str, MonitoringLogEntry] = {}
        self.pending_transactions: deque = deque()

        # ブロックチェーン設定
        self.blockchain_config = {
            'block_time_seconds': 60,  # 1分間隔
            'difficulty_adjustment': True,
            'max_block_size': 1000,  # トランザクション数
            'consensus_algorithm': 'PoW',  # Proof of Work
            'mining_reward': 1.0
        }

        # マイニング状態
        self.current_block: Optional[BlockchainBlock] = None
        self.mining_active = False

        self._lock = threading.Lock()

        # ブロックチェーンの初期化
        self._init_blockchain()

        # マイニングの開始
        self._start_mining_process()

    def _init_blockchain(self) -> None:
        """ブロックチェーンを初期化"""
        try:
            # ジェネシスブロックの作成
            if not self.blocks:
                genesis_block = self._create_genesis_block()
                self.blocks[genesis_block.block_id] = genesis_block

                logger.info(f"ジェネシスブロックを作成しました: {genesis_block.block_id}")

        except Exception as e:
            logger.error(f"ブロックチェーン初期化エラー: {e}")

    def _create_genesis_block(self) -> BlockchainBlock:
        """ジェネシスブロックを作成"""
        genesis_tx = BlockchainTransaction(
            tx_id="TX_GENESIS",
            timestamp=datetime.now(timezone.utc),
            data_hash=hashlib.sha256(b"genesis").hexdigest(),
            previous_hash="0" * 64,
            merkle_root=hashlib.sha256(b"genesis").hexdigest(),
            transaction_type="genesis",
            data_size=0
        )

        block = BlockchainBlock(
            block_id=f"BLOCK_GENESIS_{int(time.time())}",
            timestamp=datetime.now(timezone.utc),
            previous_block_hash="0" * 64,
            transactions=[genesis_tx],
            block_hash="",  # 後で計算
            nonce=0,
            difficulty=1,
            miner_id="system",
            block_size=1
        )

        # ブロックハッシュを計算
        block.block_hash = self._calculate_block_hash(block)

        return block

    def _calculate_block_hash(self, block: BlockchainBlock) -> str:
        """ブロックハッシュを計算"""
        block_data = {
            'block_id': block.block_id,
            'timestamp': block.timestamp.isoformat(),
            'previous_hash': block.previous_block_hash,
            'transactions': [tx.tx_id for tx in block.transactions],
            'nonce': block.nonce
        }

        block_string = json.dumps(block_data, sort_keys=True, default=str)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def _start_mining_process(self) -> None:
        """マイニングプロセスを開始"""
        def mining_loop():
            while True:
                try:
                    if self.mining_active and self.pending_transactions:
                        self._mine_block()
                    time.sleep(self.blockchain_config['block_time_seconds'])
                except Exception as e:
                    logger.error(f"マイニングプロセスエラー: {e}")
                    time.sleep(60)

        mining_thread = threading.Thread(target=mining_loop, daemon=True)
        mining_thread.start()
        logger.info("ブロックチェーンマイニングプロセスを開始しました。")

    def _mine_block(self) -> None:
        """ブロックをマイニング"""
        try:
            if not self.pending_transactions:
                return

            # 最新ブロックを取得
            if not self.blocks:
                return

            latest_block = max(self.blocks.values(), key=lambda b: b.timestamp)
            previous_hash = latest_block.block_hash

            # 保留中のトランザクションを取得
            transactions_to_include = []
            while self.pending_transactions and len(transactions_to_include) < self.blockchain_config['max_block_size']:
                tx = self.pending_transactions.popleft()
                transactions_to_include.append(tx)

            if not transactions_to_include:
                return

            # マークルルートを計算
            merkle_root = self._calculate_merkle_root(transactions_to_include)

            # ブロックを作成
            block = BlockchainBlock(
                block_id=f"BLOCK_{int(time.time() * 1000000)}",
                timestamp=datetime.now(timezone.utc),
                previous_block_hash=previous_hash,
                transactions=transactions_to_include,
                block_hash="",
                nonce=0,
                difficulty=self._calculate_difficulty(),
                miner_id="moni_system",
                block_size=len(transactions_to_include)
            )

            # Proof of Work（簡易版）
            block.block_hash = self._proof_of_work(block)

            # ブロックを追加
            with self._lock:
                self.blocks[block.block_id] = block

                # トランザクションを確定済みにマーク
                for tx in transactions_to_include:
                    tx.validator_nodes.append(block.miner_id)

            logger.info(f"ブロックをマイニングしました: {block.block_id} ({len(transactions_to_include)}トランザクション)")

        except Exception as e:
            logger.error(f"ブロックマイニングエラー: {e}")

    def _calculate_merkle_root(self, transactions: List[BlockchainTransaction]) -> str:
        """マークルルートを計算"""
        try:
            if not transactions:
                return hashlib.sha256(b"empty").hexdigest()

            # トランザクションハッシュのリストを作成
            tx_hashes = [tx.data_hash for tx in transactions]

            # マークルツリーを構築（簡易版）
            if len(tx_hashes) == 1:
                return tx_hashes[0]

            # ペアごとにハッシュを計算
            while len(tx_hashes) > 1:
                new_hashes = []
                for i in range(0, len(tx_hashes), 2):
                    if i + 1 < len(tx_hashes):
                        combined = tx_hashes[i] + tx_hashes[i + 1]
                    else:
                        combined = tx_hashes[i] + tx_hashes[i]  # 奇数の場合は複製

                    new_hash = hashlib.sha256(combined.encode()).hexdigest()
                    new_hashes.append(new_hash)

                tx_hashes = new_hashes

            return tx_hashes[0]

        except Exception as e:
            logger.error(f"マークルルート計算エラー: {e}")
            return hashlib.sha256(b"error").hexdigest()

    def _calculate_difficulty(self) -> int:
        """難易度を計算"""
        try:
            # 簡易的な難易度調整
            if not self.blocks:
                return 1

            # ブロック生成間隔に基づいて調整
            recent_blocks = sorted(self.blocks.values(), key=lambda b: b.timestamp)[-10:]

            if len(recent_blocks) >= 2:
                avg_interval = (recent_blocks[-1].timestamp - recent_blocks[0].timestamp).total_seconds() / (len(recent_blocks) - 1)

                if avg_interval < self.blockchain_config['block_time_seconds'] * 0.8:
                    return min(10, self.blockchain_config.get('current_difficulty', 1) + 1)
                elif avg_interval > self.blockchain_config['block_time_seconds'] * 1.2:
                    return max(1, self.blockchain_config.get('current_difficulty', 1) - 1)

            return self.blockchain_config.get('current_difficulty', 1)

        except Exception:
            return 1

    def _proof_of_work(self, block: BlockchainBlock) -> str:
        """プルーフオブワークを実行"""
        try:
            target_prefix = "0" * block.difficulty

            while True:
                block.nonce += 1
                block_hash = self._calculate_block_hash(block)

                if block_hash.startswith(target_prefix):
                    return block_hash

                # タイムアウト防止（簡易版）
                if block.nonce > 1000000:
                    logger.warning("Proof of Workがタイムアウトしました。")
                    return block_hash

        except Exception as e:
            logger.error(f"プルーフオブワークエラー: {e}")
            return self._calculate_block_hash(block)

    def add_monitoring_log(self, log_entry: MonitoringLogEntry) -> bool:
        """監視ログを追加"""
        try:
            # データの真正性を確保するためのハッシュを計算
            log_data = {
                'log_id': log_entry.log_id,
                'timestamp': log_entry.timestamp.isoformat(),
                'source': log_entry.source,
                'level': log_entry.level,
                'message': log_entry.message
            }

            data_string = json.dumps(log_data, sort_keys=True, default=str)
            log_entry.data_hash = hashlib.sha256(data_string.encode()).hexdigest()

            # トランザクションを作成
            transaction = BlockchainTransaction(
                tx_id=f"TX_LOG_{log_entry.log_id}",
                timestamp=log_entry.timestamp,
                data_hash=log_entry.data_hash,
                previous_hash=self._get_latest_transaction_hash(),
                merkle_root=log_entry.data_hash,  # 単一トランザクションの場合
                transaction_type='log_entry',
                data_size=len(data_string)
            )

            # ログエントリを保存
            with self._lock:
                self.log_entries[log_entry.log_id] = log_entry
                self.transactions[transaction.tx_id] = transaction
                self.pending_transactions.append(transaction)

            logger.info(f"監視ログをブロックチェーンに追加しました: {log_entry.log_id}")
            return True

        except Exception as e:
            logger.error(f"監視ログ追加エラー: {e}")
            return False

    def _get_latest_transaction_hash(self) -> str:
        """最新トランザクションハッシュを取得"""
        try:
            if self.transactions:
                latest_tx = max(self.transactions.values(), key=lambda t: t.timestamp)
                return latest_tx.data_hash
            return "0" * 64
        except Exception:
            return "0" * 64

    def verify_log_integrity(self, log_id: str) -> Dict[str, Any]:
        """ログ完全性を検証"""
        try:
            if log_id not in self.log_entries:
                return {'valid': False, 'error': 'ログエントリが見つかりません'}

            log_entry = self.log_entries[log_id]

            # データハッシュを再計算
            log_data = {
                'log_id': log_entry.log_id,
                'timestamp': log_entry.timestamp.isoformat(),
                'source': log_entry.source,
                'level': log_entry.level,
                'message': log_entry.message
            }

            data_string = json.dumps(log_data, sort_keys=True, default=str)
            current_hash = hashlib.sha256(data_string.encode()).hexdigest()

            # ブロックチェーン上のハッシュと比較
            is_integrity_valid = current_hash == log_entry.data_hash

            # ブロックチェーン検証
            blockchain_valid = False
            if log_entry.blockchain_tx_id and log_entry.blockchain_tx_id in self.transactions:
                tx = self.transactions[log_entry.blockchain_tx_id]
                blockchain_valid = tx.data_hash == log_entry.data_hash

            return {
                'valid': is_integrity_valid and blockchain_valid,
                'data_hash_match': is_integrity_valid,
                'blockchain_verification': blockchain_valid,
                'blockchain_tx_id': log_entry.blockchain_tx_id,
                'block_included': self._is_transaction_in_block(log_entry.blockchain_tx_id) if log_entry.blockchain_tx_id else False
            }

        except Exception as e:
            logger.error(f"ログ完全性検証エラー: {e}")
            return {'valid': False, 'error': str(e)}

    def _is_transaction_in_block(self, tx_id: str) -> bool:
        """トランザクションがブロックに含まれているかチェック"""
        try:
            for block in self.blocks.values():
                for tx in block.transactions:
                    if tx.tx_id == tx_id:
                        return True
            return False
        except Exception:
            return False

    def get_blockchain_status(self) -> Dict[str, Any]:
        """ブロックチェーンステータスを取得"""
        with self._lock:
            return {
                'total_blocks': len(self.blocks),
                'total_transactions': len(self.transactions),
                'pending_transactions': len(self.pending_transactions),
                'total_log_entries': len(self.log_entries),
                'latest_block': max(self.blocks.values(), key=lambda b: b.timestamp).block_id if self.blocks else None,
                'mining_active': self.mining_active,
                'current_difficulty': self._calculate_difficulty(),
                'block_time_seconds': self.blockchain_config['block_time_seconds']
            }

    def get_audit_trail(self, log_id: str) -> List[Dict[str, Any]]:
        """監査証跡を取得"""
        try:
            if log_id not in self.log_entries:
                return []

            log_entry = self.log_entries[log_id]

            audit_trail = [{
                'event': 'log_created',
                'timestamp': log_entry.timestamp.isoformat(),
                'description': f'ログエントリが作成されました: {log_entry.log_id}',
                'data_hash': log_entry.data_hash
            }]

            # ブロックチェーン関連イベントを追加
            if log_entry.blockchain_tx_id and log_entry.blockchain_tx_id in self.transactions:
                tx = self.transactions[log_entry.blockchain_tx_id]
                audit_trail.append({
                    'event': 'blockchain_transaction',
                    'timestamp': tx.timestamp.isoformat(),
                    'description': f'ブロックチェーンにトランザクションが記録されました: {tx.tx_id}',
                    'transaction_id': tx.tx_id,
                    'validator_nodes': tx.validator_nodes
                })

            # ブロック包含イベントを追加
            for block in self.blocks.values():
                for tx in block.transactions:
                    if tx.tx_id == log_entry.blockchain_tx_id:
                        audit_trail.append({
                            'event': 'block_mined',
                            'timestamp': block.timestamp.isoformat(),
                            'description': f'ブロックに取り込まれました: {block.block_id}',
                            'block_id': block.block_id,
                            'miner_id': block.miner_id
                        })

            return sorted(audit_trail, key=lambda x: x['timestamp'])

        except Exception as e:
            logger.error(f"監査証跡取得エラー: {e}")
            return []

    def create_immutable_log_entry(self, source: str, level: str, message: str) -> str:
        """不変ログエントリを作成"""
        try:
            log_id = f"LOG_{int(time.time() * 1000000)}"

            log_entry = MonitoringLogEntry(
                log_id=log_id,
                timestamp=datetime.now(timezone.utc),
                source=source,
                level=level,
                message=message,
                data_hash=""  # 後で計算
            )

            if self.add_monitoring_log(log_entry):
                return log_id

            return ""

        except Exception as e:
            logger.error(f"不変ログエントリ作成エラー: {e}")
            return ""

    def export_blockchain_data(self, format_type: str = 'json', file_path: Optional[Path] = None) -> Optional[str]:
        """ブロックチェーンデータをエクスポート"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = self.blockchain_dir / f"blockchain_{timestamp}.{format_type}"

        try:
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_blocks': len(self.blocks),
                    'total_transactions': len(self.transactions),
                    'total_logs': len(self.log_entries)
                },
                'blocks': [],
                'transactions': [],
                'logs': []
            }

            # ブロックデータを追加
            for block in sorted(self.blocks.values(), key=lambda b: b.timestamp):
                export_data['blocks'].append({
                    'block_id': block.block_id,
                    'timestamp': block.timestamp.isoformat(),
                    'previous_hash': block.previous_block_hash,
                    'block_hash': block.block_hash,
                    'transaction_count': len(block.transactions),
                    'difficulty': block.difficulty,
                    'miner_id': block.miner_id
                })

            # トランザクションデータを追加
            for tx in self.transactions.values():
                export_data['transactions'].append({
                    'tx_id': tx.tx_id,
                    'timestamp': tx.timestamp.isoformat(),
                    'data_hash': tx.data_hash,
                    'transaction_type': tx.transaction_type,
                    'validator_count': len(tx.validator_nodes)
                })

            # ログデータを追加
            for log_entry in self.log_entries.values():
                export_data['logs'].append({
                    'log_id': log_entry.log_id,
                    'timestamp': log_entry.timestamp.isoformat(),
                    'source': log_entry.source,
                    'level': log_entry.level,
                    'message': log_entry.message,
                    'data_hash': log_entry.data_hash,
                    'blockchain_tx_id': log_entry.blockchain_tx_id,
                    'integrity_verified': log_entry.integrity_verified
                })

            if format_type == 'json':
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, default=str)

            logger.info(f"ブロックチェーンデータをエクスポートしました: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"ブロックチェーンデータエクスポートエラー: {e}")
            return None

    def perform_integrity_audit(self) -> Dict[str, Any]:
        """完全性監査を実行"""
        try:
            audit_results = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_logs_audited': 0,
                'integrity_violations': 0,
                'blockchain_consistency': True,
                'tamper_evidence': [],
                'recommendations': []
            }

            # 全ログエントリの完全性を検証
            for log_id, log_entry in self.log_entries.items():
                audit_results['total_logs_audited'] += 1

                integrity_check = self.verify_log_integrity(log_id)

                if not integrity_check['valid']:
                    audit_results['integrity_violations'] += 1
                    audit_results['tamper_evidence'].append({
                        'log_id': log_id,
                        'violation_type': 'data_integrity' if not integrity_check['data_hash_match'] else 'blockchain_consistency',
                        'details': integrity_check
                    })

            # ブロックチェーンの一貫性を検証
            for block in self.blocks.values():
                if block.block_id != list(self.blocks.keys())[0]:  # ジェネシスブロック以外
                    # 前のブロックのハッシュが一致するかチェック
                    expected_previous_hash = self.blocks.get(f"block_{int(block.block_id.split('_')[2]) - 1}")
                    if expected_previous_hash and expected_previous_hash.block_hash != block.previous_block_hash:
                        audit_results['blockchain_consistency'] = False
                        break

            # 推奨事項の生成
            if audit_results['integrity_violations'] > 0:
                audit_results['recommendations'].append(
                    f"{audit_results['integrity_violations']}件の完全性違反を調査してください"
                )

            if not audit_results['blockchain_consistency']:
                audit_results['recommendations'].append(
                    'ブロックチェーンの一貫性に問題があります。再同期を検討してください'
                )

            audit_results['overall_integrity_score'] = (
                (audit_results['total_logs_audited'] - audit_results['integrity_violations']) /
                audit_results['total_logs_audited'] * 100
            ) if audit_results['total_logs_audited'] > 0 else 100

            return audit_results

        except Exception as e:
            logger.error(f"完全性監査エラー: {e}")
            return {'error': str(e)}


# グローバルインスタンス
blockchain_integrity_manager = BlockchainIntegrityManager()
