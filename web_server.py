import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Set, Optional
import websockets
# from internal.UAV_system.uavs_init import drones
# from internal.task_system.task_init import tasks
# from internal.airsim_server.uavsGetTask import assignments
import resource_gen

class EnhancedDroneCoordinator:
    def __init__(self):
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.last_update_time = time.time()
        self.data_generator = resource_gen.DroneDataGenerator()

        # 缓存系统状态
        self.cached_resources: Optional[List[Dict]] = None
        self.cached_progress: Optional[List[Dict]] = None
        self.cached_statistics: Optional[Dict] = None
        self.cached_metrics: Optional[Dict] = None
        self.cached_tasksResource: Optional[Dict] = None

    def _generate_resources(self) -> List[Dict]:
        """从DroneDataGenerator获取无人机资源数据"""
        return self.data_generator.get_drone_data()

    def _generate_progress(self) -> List[Dict]:
        """生成符合TaskProgress接口的进度数据"""
        progress_data = []
        #每次对所有任务记进行遍历
        for task in tasks:
            # 获取执行该任务的无人机ID列表
            assigned_drones = assignments.get("_task_index", {}).get(task.task_id, [])
            for drone_id in assigned_drones:
                progress_data.append({
                    "taskId": str(task.task_id),
                    "droneId": drone_id,
                    "taskName": task.name,
                    "progress": round((task.duration - task.surplus) / task.duration * 100, 1)
                })
        #print(progress_data)
        return progress_data

    def _calculate_statistics(self) -> Dict:
        """计算任务统计信息"""
        status_count = {0: 0, 1: 0, 2: 0, 3: 0}
        for task in tasks:
            status_count[task.status] += 1
        #print(json.dumps(status_count))
        return {
            "notStarted": status_count[0],
            "inProgress": status_count[1],
            "completed": status_count[2],
            "failed": status_count[3]
        }

    def _calculate_metrics(self) -> Dict:
        """生成系统性能指标"""
        return {
            "totalDrones": len(self.data_generator.drones),
            "responseTime": round((time.time() - self.last_update_time) * 1000, 1)
        }

    def _generate_tasksResource(self) -> List[Dict]:
        Tstatus_map = {
            0: 'noStart',
            1: 'assigned',
            2: 'running',
            3: 'breaking',
            4: 'end'
        }
        """生成任务数据"""
        return [{
            "id": task.task_id,
            "tx": task.x,
            "ty": task.y,
            "Tstatus": Tstatus_map.get(task.status, '未知状态')
        } for task in tasks]

    async def _send_data(self, msg_type: str, data: any):
        """统一数据发送方法"""
        if self.connected_clients:
            message = json.dumps({
                "type": msg_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            })

            await asyncio.gather(*[
                client.send(message)
                for client in self.connected_clients
            ])

    async def broadcast_updates(self):
        """智能广播更新"""
        while True:
            try:
                # 生成最新数据
                new_res = self._generate_resources()
                new_prog = self._generate_progress()
                new_stat = self._calculate_statistics()
                new_met = self._calculate_metrics()
                new_tas = self._generate_tasksResource()
                #print(new_tas)

                # 发送更新
                await self._send_data("resources", new_res)
                await self._send_data("progress", new_prog)
                await self._send_data("statistics", new_stat)
                await self._send_data("metrics", new_met)
                await self._send_data("tasksData", new_tas)

                self.last_update_time = time.time()
                await asyncio.sleep(0.5)  # 固定500ms更新间隔

            except Exception as e:
                print(f"广播异常: {str(e)}")
                await asyncio.sleep(1)  # 错误恢复间隔

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """处理客户端连接生命周期"""
        self.connected_clients.add(websocket)
        try:
            async for message in websocket:
                # 预留控制指令处理接口
                if message == "ping":
                    await websocket.send("pong")
        except websockets.ConnectionClosed:
            pass
        finally:
            self.connected_clients.remove(websocket)


async def main():
    coordinator = EnhancedDroneCoordinator()

    # 配置WebSocket服务器参数
    server_config = {
        "host": "localhost",
        "port": 8080,
        "ping_interval": 20,  # 20秒心跳间隔
        "ping_timeout": 40,  # 40秒超时
        "max_queue": 1024  # 最大连接队列
    }

    async with websockets.serve(
            coordinator.handle_client,
            **server_config
    ):
        print(f"WS服务已启动 ws://{server_config['host']}:{server_config['port']}")
        await coordinator.broadcast_updates()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("服务已安全终止")
