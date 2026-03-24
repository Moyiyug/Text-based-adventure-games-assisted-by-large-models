import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/Table";
import { useAdminStories, useRagConfigs } from "../../hooks/useAdminApi";
import {
  useEvalResults,
  useEvalRun,
  useEvalRunsList,
  useSampleEvalSessions,
  useStartEvalRun,
} from "../../hooks/useAdminEvalPromptsSessions";
import { toast, toastApiError } from "../../lib/toast";
import { cn } from "../../lib/utils";
import type { EvalRunOut, EvalResultOut } from "../../types/eval";

function formatDt(iso: string | null | undefined) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function scoreCell(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toFixed(3);
}

export default function AdminEvalPage() {
  const { data: stories = [] } = useAdminStories(false);
  const { data: ragConfigs = [] } = useRagConfigs();

  const [storyId, setStoryId] = useState<number | "">("");
  const [ragConfigId, setRagConfigId] = useState<number | "">("");
  const [generateCases, setGenerateCases] = useState(true);
  const [caseIdsRaw, setCaseIdsRaw] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [sampleSessionId, setSampleSessionId] = useState("");
  const [sampleMaxTurns, setSampleMaxTurns] = useState("8");

  const [listSv, setListSv] = useState("");
  const [listStatus, setListStatus] = useState("");
  const [listOffset, setListOffset] = useState(0);
  const listLimit = 30;

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [pollingRunId, setPollingRunId] = useState<number | null>(null);

  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");

  const [expandedResultId, setExpandedResultId] = useState<number | null>(null);

  const activeVersionId = useMemo(() => {
    if (storyId === "") return null;
    const s = stories.find((x) => x.id === storyId);
    return s?.active_version_id ?? null;
  }, [storyId, stories]);

  const listParams = useMemo(() => {
    const p: { story_version_id?: number; status?: string; limit: number; offset: number } = {
      limit: listLimit,
      offset: listOffset,
    };
    if (listSv.trim()) {
      const n = parseInt(listSv, 10);
      if (!Number.isNaN(n)) p.story_version_id = n;
    }
    if (listStatus.trim()) p.status = listStatus.trim();
    return p;
  }, [listSv, listStatus, listOffset]);

  const { data: runsData, isLoading: runsLoading } = useEvalRunsList(listParams);
  const { data: resultsData } = useEvalResults(selectedRunId);
  const { data: pollRun } = useEvalRun(pollingRunId);

  const startMut = useStartEvalRun();
  const sampleMut = useSampleEvalSessions();

  const compareRunA = useEvalRun(compareA.trim() ? parseInt(compareA, 10) : null);
  const compareRunB = useEvalRun(compareB.trim() ? parseInt(compareB, 10) : null);

  const handleStart = async () => {
    if (ragConfigId === "") {
      toast.error("请选择 RAG 方案");
      return;
    }
    if (activeVersionId == null) {
      toast.error("请选择已入库且有活跃版本的作品");
      return;
    }
    const explicitIds = showAdvanced && caseIdsRaw.trim() !== "";
    let case_ids: number[] | null | undefined = undefined;
    if (explicitIds) {
      case_ids = caseIdsRaw
        .split(/[,，\s]+/)
        .map((x) => x.trim())
        .filter(Boolean)
        .map((x) => parseInt(x, 10))
        .filter((n) => !Number.isNaN(n));
    }
    try {
      const res = await startMut.mutateAsync({
        rag_config_id: Number(ragConfigId),
        story_version_id: activeVersionId,
        generate_cases: !explicitIds && generateCases,
        case_ids: explicitIds ? case_ids : undefined,
      });
      toast.success(`评测已排队 · run #${res.run_id}`);
      setPollingRunId(res.run_id);
      setSelectedRunId(res.run_id);
    } catch (e) {
      toastApiError(e, "发起评测失败");
    }
  };

  const handleSample = async () => {
    const sid = parseInt(sampleSessionId, 10);
    if (Number.isNaN(sid)) {
      toast.error("请输入有效会话 ID");
      return;
    }
    const mt = parseInt(sampleMaxTurns, 10);
    try {
      const res = await sampleMut.mutateAsync({
        session_id: sid,
        max_turns: Number.isNaN(mt) ? 8 : Math.min(50, Math.max(1, mt)),
      });
      toast.success(`会话抽样评测已排队 · run #${res.run_id}`);
      setPollingRunId(res.run_id);
      setSelectedRunId(res.run_id);
    } catch (e) {
      toastApiError(e, "抽样评测失败");
    }
  };

  const runs = runsData?.items ?? [];
  const totalRuns = runsData?.total ?? 0;

  return (
    <div className="min-w-[1024px] p-8">
      <header className="mb-8">
        <h1 className="font-story text-2xl font-bold text-text-primary">评测面板</h1>
        <p className="mt-1 text-sm text-text-secondary">
          在后台排队跑 RAG 评测任务；完成后在列表中查看分数与评委理由，并可对比两次 run 的均分。
        </p>
        <ol className="mt-3 list-inside list-decimal space-y-1 text-xs text-text-secondary">
          <li>在下方「发起评测」或「会话抽样评测」提交任务，页面顶部会出现最近 run 的状态（进行中约每 2 秒刷新）。</li>
          <li>在「评测运行列表」用版本 ID、状态筛选，点击某行的 id 加载该 run 的逐题结果。</li>
          <li>可选：把两个 run 的 id 填入「方案对比」并排查看均分与状态。</li>
        </ol>
      </header>

      {pollingRunId != null && pollRun && (
        <div
          className={cn(
            "mb-6 rounded-xl border px-4 py-3 text-sm",
            pollRun.status === "failed"
              ? "border-danger/40 bg-danger/10 text-danger"
              : pollRun.status === "completed"
                ? "border-success/40 bg-success/10 text-text-primary"
                : "border-border bg-bg-secondary text-text-secondary"
          )}
        >
          <span className="font-medium text-text-primary">最近排队 Run #{pollingRunId}</span> · 状态{" "}
          <strong>{pollRun.status}</strong>
          {pollRun.status === "pending" || pollRun.status === "running" ? "（约每 2 秒自动刷新）" : null}
          {pollRun.error_message ? (
            <p className="mt-1 text-xs text-danger">{pollRun.error_message}</p>
          ) : null}
        </div>
      )}

      <div className="mb-10 grid gap-8 lg:grid-cols-2 lg:items-stretch">
        <section className="flex min-h-0 flex-col rounded-xl border border-border bg-bg-secondary/50 p-5 shadow-sm">
          <h2 className="font-ui text-base font-semibold text-text-primary">发起评测</h2>
          <p className="mt-2 text-xs text-text-secondary">
            依赖作品的<strong className="font-medium text-text-primary">活跃版本</strong>（入库成功后的当前版本）。
            勾选「自动生成」时由 DeepSeek 根据正文线索写入评测用例再跑检索+生成+评委；在高级中填写{" "}
            <code className="rounded bg-bg-primary px-1 font-mono text-[10px]">case_ids</code>{" "}
            且非空时，将<strong className="text-text-primary">不再</strong>自动生成，只跑你指定的用例 id。
          </p>
          <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3">
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-text-secondary">作品</label>
                <select
                  className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
                  value={storyId === "" ? "" : String(storyId)}
                  onChange={(e) => setStoryId(e.target.value ? parseInt(e.target.value, 10) : "")}
                >
                  <option value="">选择作品…</option>
                  {stories.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                      {s.active_version_id ? "" : "（无活跃版本）"}
                    </option>
                  ))}
                </select>
                {storyId !== "" && activeVersionId == null && (
                  <p className="mt-1 text-xs text-warning">该作品暂无活跃版本，请先完成入库。</p>
                )}
                {activeVersionId != null && (
                  <p className="mt-1 text-xs text-text-secondary">将使用版本 ID：{activeVersionId}</p>
                )}
              </div>
              <div>
                <label className="mb-1 block text-xs text-text-secondary">RAG 方案</label>
                <select
                  className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
                  value={ragConfigId === "" ? "" : String(ragConfigId)}
                  onChange={(e) => setRagConfigId(e.target.value ? parseInt(e.target.value, 10) : "")}
                >
                  <option value="">选择方案…</option>
                  {ragConfigs.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.variant_type})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2 rounded-lg border border-border/60 bg-bg-primary/40 p-3">
              <p className="text-xs text-text-secondary">
                用例来源：二选一——勾选下面自动生成，或展开高级填写已有{" "}
                <code className="font-mono text-[10px]">case_ids</code>（与自动生成互斥）。
              </p>
              <label className="flex cursor-pointer items-start gap-2 text-sm text-text-primary">
                <input
                  type="checkbox"
                  className="mt-0.5 shrink-0"
                  checked={generateCases}
                  onChange={(e) => setGenerateCases(e.target.checked)}
                  disabled={showAdvanced && caseIdsRaw.trim() !== ""}
                />
                <span>自动生成测试用例（DeepSeek）</span>
              </label>
              <button
                type="button"
                className="text-left text-xs text-accent-primary underline decoration-accent-primary/50 hover:decoration-accent-primary"
                onClick={() => setShowAdvanced((v) => !v)}
              >
                {showAdvanced ? "收起高级选项" : "高级：指定 case_ids（逗号分隔）"}
              </button>
              {showAdvanced && (
                <div className="pt-1">
                  <label className="mb-1 block text-xs text-text-secondary">
                    用例 ID（逗号或空格分隔；留空则仍按上方勾选逻辑）
                  </label>
                  <Input
                    value={caseIdsRaw}
                    onChange={(e) => setCaseIdsRaw(e.target.value)}
                    placeholder="例如 1,2,3"
                  />
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
            <Button
              className="w-full sm:w-auto"
              onClick={() => void handleStart()}
              isLoading={startMut.isPending}
              disabled={activeVersionId == null || ragConfigId === ""}
            >
              提交评测
            </Button>
          </div>
        </section>

        <section className="flex min-h-0 flex-col rounded-xl border border-border bg-bg-secondary/50 p-5 shadow-sm">
          <h2 className="font-ui text-base font-semibold text-text-primary">会话抽样评测</h2>
          <p className="mt-2 text-xs text-text-secondary">
            与左侧不同：不重新生成答案，而是按回合抽取<strong className="text-text-primary">玩家句 + 历史 GM 回复</strong>
            ，用玩家句做检索 query，把库里已有的 GM 正文当作待评「生成物」打分（后端类型{" "}
            <code className="rounded bg-bg-primary px-1 font-mono text-[10px]">session_turn</code>）。
          </p>
          <p className="mt-2 text-xs text-text-secondary">
            <strong className="font-medium text-text-primary">会话 ID</strong> 可在「会话查看」页列表的 id 列找到，或查库表{" "}
            <code className="font-mono text-[10px]">sessions.id</code>。<strong className="font-medium text-text-primary">
              最多抽样轮数
            </strong>{" "}
            表示参与评测的回合上限（1–50），实际条数受对话长度与抽样策略影响。
          </p>
          <div className="mt-4 flex flex-1 flex-col gap-3">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">会话 ID</label>
              <Input
                value={sampleSessionId}
                onChange={(e) => setSampleSessionId(e.target.value)}
                placeholder="sessions.id"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">最多抽样轮数</label>
              <Input
                value={sampleMaxTurns}
                onChange={(e) => setSampleMaxTurns(e.target.value)}
                placeholder="1–50"
              />
            </div>
          </div>
          <div className="mt-4 border-t border-border pt-4">
            <Button
              className="w-full sm:w-auto"
              onClick={() => void handleSample()}
              isLoading={sampleMut.isPending}
              variant="secondary"
            >
              提交抽样评测
            </Button>
          </div>
        </section>
      </div>

      <section className="mb-10 rounded-xl border border-border bg-bg-secondary/50 p-5 shadow-sm">
        <h2 className="font-ui text-base font-semibold text-text-primary">方案对比（MVP）</h2>
        <p className="mt-2 text-xs text-text-secondary">
          在下方「评测运行列表」的 <strong className="text-text-primary">ID</strong> 列复制两个{" "}
          <code className="font-mono text-[10px]">run_id</code> 填入左右框。建议两次评测针对<strong className="text-text-primary">
            同一 story_version
          </strong>
          ，便于对照均分。当前 MVP 仅并排展示指标与状态，<strong className="text-text-primary">不做</strong>逐题一一对齐。
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Run A</label>
            <Input value={compareA} onChange={(e) => setCompareA(e.target.value)} className="w-32" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">Run B</label>
            <Input value={compareB} onChange={(e) => setCompareB(e.target.value)} className="w-32" />
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <CompareCard label="A" run={compareRunA.data} loading={compareRunA.isLoading} />
          <CompareCard label="B" run={compareRunB.data} loading={compareRunB.isLoading} />
        </div>
      </section>

      <section className="mb-8">
        <p className="mb-3 text-xs text-text-secondary">
          点击表格中的<strong className="text-text-primary">一行</strong>可选中该 run，并在页面底部「运行结果明细」加载逐题分数与展开详情。可用{" "}
          <code className="font-mono text-[10px]">story_version_id</code>、<code className="font-mono text-[10px]">status</code>{" "}
          （如 pending、running、completed、failed）筛选后翻页浏览。
        </p>
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <h2 className="font-ui text-base font-semibold text-text-primary">评测运行列表</h2>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">版本 ID</label>
            <Input
              value={listSv}
              onChange={(e) => setListSv(e.target.value)}
              className="w-36"
              placeholder="可选"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">状态</label>
            <Input
              value={listStatus}
              onChange={(e) => setListStatus(e.target.value)}
              className="w-32"
              placeholder="pending…"
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setListOffset(Math.max(0, listOffset - listLimit));
            }}
            disabled={listOffset <= 0}
          >
            上一页
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              if (listOffset + listLimit < totalRuns) setListOffset(listOffset + listLimit);
            }}
            disabled={listOffset + listLimit >= totalRuns}
          >
            下一页
          </Button>
          <span className="text-xs text-text-secondary">
            {totalRuns ? `${listOffset + 1}–${Math.min(listOffset + listLimit, totalRuns)} / ${totalRuns}` : ""}
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>方案</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>题数</TableHead>
                <TableHead>忠实性</TableHead>
                <TableHead>叙事</TableHead>
                <TableHead>创建</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runsLoading ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-text-secondary">
                    加载中…
                  </TableCell>
                </TableRow>
              ) : runs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-text-secondary">
                    暂无数据
                  </TableCell>
                </TableRow>
              ) : (
                runs.map((r) => (
                  <TableRow
                    key={r.id}
                    className={cn(
                      "cursor-pointer",
                      selectedRunId === r.id ? "bg-bg-hover/80" : undefined
                    )}
                    onClick={() => setSelectedRunId(r.id)}
                  >
                    <TableCell className="font-mono text-xs">{r.id}</TableCell>
                    <TableCell className="text-xs">{r.story_version_id}</TableCell>
                    <TableCell className="text-xs">{r.rag_config_id}</TableCell>
                    <TableCell className="text-xs">{r.status}</TableCell>
                    <TableCell className="text-xs">{r.total_cases}</TableCell>
                    <TableCell className="text-xs">{scoreCell(r.avg_faithfulness)}</TableCell>
                    <TableCell className="text-xs">{scoreCell(r.avg_story_quality)}</TableCell>
                    <TableCell className="text-xs">{formatDt(r.created_at)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-bg-secondary/50 p-5 shadow-sm">
        <h2 className="font-ui text-base font-semibold text-text-primary">
          运行结果明细
          {selectedRunId != null ? ` · Run #${selectedRunId}` : ""}
        </h2>
        {!selectedRunId ? (
          <p className="mt-2 text-sm text-text-secondary">在上方列表中点击一行以加载结果</p>
        ) : !resultsData?.items.length ? (
          <p className="mt-2 text-sm text-text-secondary">暂无结果（可能仍在运行或失败）</p>
        ) : (
          <div className="mt-4 space-y-2">
            {resultsData.items.map((row) => (
              <ResultExpandBlock
                key={row.id}
                row={row}
                open={expandedResultId === row.id}
                onToggle={() =>
                  setExpandedResultId((id) => (id === row.id ? null : row.id))
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function CompareCard({
  label,
  run,
  loading,
}: {
  label: string;
  run: EvalRunOut | undefined;
  loading: boolean;
}) {
  if (loading) return <div className="text-sm text-text-secondary">Run {label} 加载中…</div>;
  if (!run) return <div className="text-sm text-text-secondary">Run {label}：未加载</div>;
  return (
    <div className="rounded-lg border border-border bg-bg-primary p-4 text-sm">
      <p className="font-medium text-text-primary">Run {label} · #{run.id}</p>
      <ul className="mt-2 space-y-1 text-text-secondary">
        <li>状态：{run.status}</li>
        <li>题数：{run.total_cases}</li>
        <li>忠实性均分：{scoreCell(run.avg_faithfulness)}</li>
        <li>叙事均分：{scoreCell(run.avg_story_quality)}</li>
        {run.error_message ? <li className="text-danger">{run.error_message}</li> : null}
      </ul>
    </div>
  );
}

function ResultExpandBlock({
  row,
  open,
  onToggle,
}: {
  row: EvalResultOut;
  open: boolean;
  onToggle: () => void;
}) {
  const q = row.case?.question?.slice(0, 80) ?? `case #${row.eval_case_id}`;
  return (
    <div className="rounded-lg border border-border bg-bg-primary">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-text-primary hover:bg-bg-hover/60"
      >
        {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
        <span className="font-mono text-xs text-text-secondary">#{row.id}</span>
        <span className="truncate">{q}</span>
        <span className="ml-auto shrink-0 text-xs text-text-secondary">
          F {scoreCell(row.faithfulness_score)} / Q {scoreCell(row.story_quality_score)}
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-border px-3 py-3 text-xs text-text-secondary">
          {row.case ? (
            <p>
              <span className="font-medium text-text-primary">类型</span> {row.case.case_type}
            </p>
          ) : null}
          {row.case?.rubric ? (
            <p>
              <span className="font-medium text-text-primary">Rubric</span> {row.case.rubric}
            </p>
          ) : null}
          <p>
            <span className="font-medium text-text-primary">评委理由</span> {row.judge_reasoning ?? "—"}
          </p>
          <div>
            <span className="font-medium text-text-primary">模型回答摘要</span>
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-bg-secondary p-2 font-mono text-[11px]">
              {row.generated_answer.slice(0, 4000)}
              {row.generated_answer.length > 4000 ? "…" : ""}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
