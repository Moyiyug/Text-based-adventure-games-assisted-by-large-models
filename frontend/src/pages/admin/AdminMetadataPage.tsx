import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ActionMenu } from "../../components/ui/ActionMenu";
import { Button } from "../../components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "../../components/ui/Dialog";
import { Input } from "../../components/ui/Input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/Table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/Tabs";
import {
  useAdminStories,
  useChapterSceneMutations,
  useEntityMutations,
  useMetadataChapters,
  useSceneDetail,
  useMetadataEntities,
  useMetadataRelationships,
  useMetadataRisk,
  useMetadataTimeline,
  useRelationshipMutations,
  useRiskMutations,
  useTimelineMutations,
} from "../../hooks/useAdminApi";
import { toast, toastApiError } from "../../lib/toast";
import { cn } from "../../lib/utils";
import type { ChapterRow, EntityRow, RelationshipRow, RiskRow, TimelineRow } from "../../api/adminMetadata";

const fieldClass =
  "flex min-h-[44px] w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary/20";

function MetadataEditor({ storyId }: { storyId: number }) {
  const { data: stories } = useAdminStories(false);
  const story = stories?.find((s) => s.id === storyId);
  const ingesting = story?.status === "ingesting";

  const entitiesQ = useMetadataEntities(storyId);
  const relQ = useMetadataRelationships(storyId);
  const tlQ = useMetadataTimeline(storyId);
  const chQ = useMetadataChapters(storyId);
  const riskQ = useMetadataRisk(storyId);

  const em = useEntityMutations(storyId);
  const rm = useRelationshipMutations(storyId);
  const tm = useTimelineMutations(storyId);
  const csm = useChapterSceneMutations(storyId);
  const riskM = useRiskMutations(storyId);

  const flatScenes = useMemo(() => {
    const ch = chQ.data ?? [];
    return ch.flatMap((c) =>
      c.scenes.map((s) => ({
        ...s,
        chapter_id: c.id,
        chapter_number: c.chapter_number,
      }))
    );
  }, [chQ.data]);

  /* --- Entity dialog --- */
  const [entOpen, setEntOpen] = useState(false);
  const [entEdit, setEntEdit] = useState<EntityRow | null>(null);
  const [fName, setFName] = useState("");
  const [fCanon, setFCanon] = useState("");
  const [fType, setFType] = useState("character");
  const [fDesc, setFDesc] = useState("");
  const [fAliases, setFAliases] = useState("");

  const openNewEntity = () => {
    setEntEdit(null);
    setFName("");
    setFCanon("");
    setFType("character");
    setFDesc("");
    setFAliases("");
    setEntOpen(true);
  };
  const openEditEntity = (e: EntityRow) => {
    setEntEdit(e);
    setFName(e.name);
    setFCanon(e.canonical_name);
    setFType(e.entity_type);
    setFDesc(e.description ?? "");
    setFAliases((e.aliases || []).join(", "));
    setEntOpen(true);
  };
  const saveEntity = async () => {
    const aliases = fAliases
      .split(/[,，]/)
      .map((x) => x.trim())
      .filter(Boolean);
    try {
      if (entEdit) {
        await em.update.mutateAsync({
          id: entEdit.id,
          body: {
            name: fName.trim(),
            canonical_name: fCanon.trim(),
            entity_type: fType.trim(),
            description: fDesc.trim() || null,
            aliases,
          },
        });
        toast.success("实体已更新");
      } else {
        await em.create.mutateAsync({
          name: fName.trim(),
          canonical_name: fCanon.trim(),
          entity_type: fType.trim(),
          description: fDesc.trim() || undefined,
          aliases,
        });
        toast.success("实体已创建");
      }
      setEntOpen(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  /* --- Relationship dialog --- */
  const [relOpen, setRelOpen] = useState(false);
  const [relEdit, setRelEdit] = useState<RelationshipRow | null>(null);
  const [rA, setRA] = useState("");
  const [rB, setRB] = useState("");
  const [rType, setRType] = useState("");
  const [rDesc, setRDesc] = useState("");
  const [rConf, setRConf] = useState("1");

  const openNewRel = () => {
    setRelEdit(null);
    setRA("");
    setRB("");
    setRType("");
    setRDesc("");
    setRConf("1");
    setRelOpen(true);
  };
  const openEditRel = (r: RelationshipRow) => {
    setRelEdit(r);
    setRA(String(r.entity_a_id));
    setRB(String(r.entity_b_id));
    setRType(r.relationship_type);
    setRDesc(r.description ?? "");
    setRConf(String(r.confidence));
    setRelOpen(true);
  };
  const saveRel = async () => {
    const a = Number(rA);
    const b = Number(rB);
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      toast.error("请选择有效实体 ID");
      return;
    }
    try {
      if (relEdit) {
        await rm.update.mutateAsync({
          id: relEdit.id,
          body: {
            relationship_type: rType.trim(),
            description: rDesc.trim() || null,
            confidence: Number(rConf) || 1,
          },
        });
        toast.success("关系已更新");
      } else {
        await rm.create.mutateAsync({
          entity_a_id: a,
          entity_b_id: b,
          relationship_type: rType.trim(),
          description: rDesc.trim() || undefined,
          confidence: Number(rConf) || 1,
        });
        toast.success("关系已创建");
      }
      setRelOpen(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  /* --- Timeline dialog --- */
  const [tlOpen, setTlOpen] = useState(false);
  const [tlEdit, setTlEdit] = useState<TimelineRow | null>(null);
  const [tDesc, setTDesc] = useState("");
  const [tOrder, setTOrder] = useState("0");
  const [tCh, setTCh] = useState("");
  const [tSc, setTSc] = useState("");
  const [tPart, setTPart] = useState("");

  const openNewTl = () => {
    setTlEdit(null);
    setTDesc("");
    setTOrder("0");
    setTCh("");
    setTSc("");
    setTPart("");
    setTlOpen(true);
  };
  const openEditTl = (t: TimelineRow) => {
    setTlEdit(t);
    setTDesc(t.event_description);
    setTOrder(String(t.order_index));
    setTCh(t.chapter_id != null ? String(t.chapter_id) : "");
    setTSc(t.scene_id != null ? String(t.scene_id) : "");
    setTPart((t.participants || []).join(","));
    setTlOpen(true);
  };
  const saveTl = async () => {
    const parts = tPart
      .split(/[,，]/)
      .map((x) => Number(x.trim()))
      .filter((x) => Number.isFinite(x));
    const body = {
      event_description: tDesc.trim(),
      order_index: Number(tOrder) || 0,
      chapter_id: tCh.trim() === "" ? null : Number(tCh),
      scene_id: tSc.trim() === "" ? null : Number(tSc),
      participants: parts,
    };
    try {
      if (tlEdit) {
        await tm.update.mutateAsync({ id: tlEdit.id, body });
        toast.success("事件已更新");
      } else {
        await tm.create.mutateAsync(body);
        toast.success("事件已创建");
      }
      setTlOpen(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  /* --- Chapter / Scene --- */
  const [chOpen, setChOpen] = useState(false);
  const [chEdit, setChEdit] = useState<ChapterRow | null>(null);
  const [chTitle, setChTitle] = useState("");
  const [chSum, setChSum] = useState("");

  const [scOpen, setScOpen] = useState(false);
  const [scId, setScId] = useState<number | null>(null);
  const [scSum, setScSum] = useState("");
  const [scRaw, setScRaw] = useState("");
  const [scOrig, setScOrig] = useState<{ raw: string; sum: string }>({ raw: "", sum: "" });

  const scDetailQ = useSceneDetail(storyId, scId, scOpen);

  useEffect(() => {
    if (scDetailQ.data) {
      const r = scDetailQ.data.raw_text;
      const s = scDetailQ.data.summary ?? "";
      setScRaw(r);
      setScSum(s);
      setScOrig({ raw: r, sum: s });
    }
  }, [scDetailQ.data]);

  const openEditCh = (c: ChapterRow) => {
    setChEdit(c);
    setChTitle(c.title ?? "");
    setChSum(c.summary ?? "");
    setChOpen(true);
  };
  const saveCh = async () => {
    if (!chEdit) return;
    try {
      await csm.updateChapter.mutateAsync({
        chapterId: chEdit.id,
        body: { title: chTitle.trim() || null, summary: chSum.trim() || null },
      });
      toast.success("章节已保存");
      setChOpen(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  const openEditSc = (sceneId: number) => {
    setScId(sceneId);
    setScSum("");
    setScRaw("");
    setScOrig({ raw: "", sum: "" });
    setScOpen(true);
  };
  const saveSc = async () => {
    if (scId == null) return;
    try {
      const body: { summary?: string | null; raw_text?: string } = {};
      const sumTrim = scSum.trim();
      const origSum = (scOrig.sum || "").trim();
      if (sumTrim !== origSum) body.summary = sumTrim || null;
      if (scRaw !== scOrig.raw) body.raw_text = scRaw;
      if (Object.keys(body).length === 0) {
        toast("无任何修改", { duration: 2000 });
        return;
      }
      const res = await csm.updateScene.mutateAsync({
        sceneId: scId,
        body,
      });
      if (res.data.warnings?.length) {
        toast(`向量提示：${res.data.warnings.join("；")}`, { duration: 6000 });
      }
      toast.success(
        "raw_text" in body ? "场景已保存（已重建切块并尝试写入向量）" : "场景已保存"
      );
      setScOpen(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  /* --- Risk --- */
  const [riskOpen, setRiskOpen] = useState(false);
  const [riskEdit, setRiskEdit] = useState<RiskRow | null>(null);
  const [riskRw, setRiskRw] = useState("");
  const openRisk = (r: RiskRow) => {
    setRiskEdit(r);
    setRiskRw(r.rewritten_text);
    setRiskOpen(true);
  };
  const saveRisk = async () => {
    if (!riskEdit) return;
    try {
      await riskM.mutateAsync({
        segmentId: riskEdit.id,
        body: { rewritten_text: riskRw.trim() },
      });
      toast.success("已保存改写文本");
      setRiskOpen(false);
    } catch (e) {
      toastApiError(e, "保存失败");
    }
  };

  const entities = entitiesQ.data ?? [];

  return (
    <div className="space-y-6">
      {ingesting && (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-text-primary"
          role="status"
        >
          该作品正在入库，编辑元数据可能返回 409。建议等待状态变为「已就绪」后再改。
        </div>
      )}

      <Tabs defaultValue="entities">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="entities">实体</TabsTrigger>
          <TabsTrigger value="relationships">关系</TabsTrigger>
          <TabsTrigger value="timeline">时间线</TabsTrigger>
          <TabsTrigger value="chapters">章节</TabsTrigger>
          <TabsTrigger value="scenes">场景</TabsTrigger>
          <TabsTrigger value="risk">敏感段落</TabsTrigger>
        </TabsList>

        <TabsContent value="entities">
          <div className="mb-4 flex justify-end">
            <Button size="sm" onClick={openNewEntity}>
              新增实体
            </Button>
          </div>
          {entitiesQ.isLoading ? (
            <p className="text-sm text-text-secondary">加载中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>标准名</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="w-20 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entities.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="font-mono text-xs">{e.id}</TableCell>
                    <TableCell>{e.name}</TableCell>
                    <TableCell className="text-text-secondary">{e.canonical_name}</TableCell>
                    <TableCell>{e.entity_type}</TableCell>
                    <TableCell className="text-right">
                      <ActionMenu
                        items={[
                          { label: "编辑", onSelect: () => openEditEntity(e) },
                          {
                            label: "删除",
                            destructive: true,
                            onSelect: async () => {
                              if (!confirm(`删除实体 #${e.id}？`)) return;
                              try {
                                await em.remove.mutateAsync(e.id);
                                toast.success("已删除");
                              } catch (err) {
                                toastApiError(err, "删除失败");
                              }
                            },
                          },
                        ]}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="relationships">
          <div className="mb-4 flex justify-end">
            <Button size="sm" onClick={openNewRel}>
              新增关系
            </Button>
          </div>
          {relQ.isLoading ? (
            <p className="text-sm text-text-secondary">加载中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>A</TableHead>
                  <TableHead>B</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead className="w-20 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(relQ.data ?? []).map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">{r.id}</TableCell>
                    <TableCell>{r.entity_a_id}</TableCell>
                    <TableCell>{r.entity_b_id}</TableCell>
                    <TableCell>{r.relationship_type}</TableCell>
                    <TableCell className="text-right">
                      <ActionMenu
                        items={[
                          { label: "编辑", onSelect: () => openEditRel(r) },
                          {
                            label: "删除",
                            destructive: true,
                            onSelect: async () => {
                              if (!confirm(`删除关系 #${r.id}？`)) return;
                              try {
                                await rm.remove.mutateAsync(r.id);
                                toast.success("已删除");
                              } catch (err) {
                                toastApiError(err, "删除失败");
                              }
                            },
                          },
                        ]}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="timeline">
          <div className="mb-4 flex justify-end">
            <Button size="sm" onClick={openNewTl}>
              新增事件
            </Button>
          </div>
          {tlQ.isLoading ? (
            <p className="text-sm text-text-secondary">加载中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>序</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>章/场</TableHead>
                  <TableHead className="w-20 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(tlQ.data ?? []).map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>{t.order_index}</TableCell>
                    <TableCell className="max-w-md truncate">{t.event_description}</TableCell>
                    <TableCell className="text-xs text-text-secondary">
                      ch {t.chapter_id ?? "—"} / sc {t.scene_id ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <ActionMenu
                        items={[
                          { label: "编辑", onSelect: () => openEditTl(t) },
                          {
                            label: "删除",
                            destructive: true,
                            onSelect: async () => {
                              if (!confirm(`删除事件 #${t.id}？`)) return;
                              try {
                                await tm.remove.mutateAsync(t.id);
                                toast.success("已删除");
                              } catch (err) {
                                toastApiError(err, "删除失败");
                              }
                            },
                          },
                        ]}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="chapters">
          {chQ.isLoading ? (
            <p className="text-sm text-text-secondary">加载中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>标题</TableHead>
                  <TableHead>摘要</TableHead>
                  <TableHead className="w-20 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(chQ.data ?? []).map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>{c.chapter_number}</TableCell>
                    <TableCell>{c.title ?? "—"}</TableCell>
                    <TableCell className="max-w-md truncate text-text-secondary">{c.summary ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="secondary" onClick={() => openEditCh(c)}>
                        编辑
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="scenes">
          {chQ.isLoading ? (
            <p className="text-sm text-text-secondary">加载中…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>章</TableHead>
                  <TableHead>场</TableHead>
                  <TableHead>摘要</TableHead>
                  <TableHead className="w-24 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flatScenes.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>{s.chapter_number}</TableCell>
                    <TableCell>{s.scene_number}</TableCell>
                    <TableCell className="max-w-lg truncate text-text-secondary">{s.summary ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <ActionMenu
                        items={[
                          { label: "编辑场景", onSelect: () => openEditSc(s.id) },
                          {
                            label: "删除场景",
                            destructive: true,
                            onSelect: async () => {
                              if (
                                !confirm(
                                  `删除章 ${s.chapter_number} 场 ${s.scene_number}？将同时删除该场景下向量切块且不可恢复。`
                                )
                              )
                                return;
                              try {
                                await csm.deleteScene.mutateAsync(s.id);
                                toast.success("已删除场景");
                              } catch (err) {
                                toastApiError(err, "删除失败");
                              }
                            },
                          },
                        ]}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="risk">
          {riskQ.isLoading ? (
            <p className="text-sm text-text-secondary">加载中…</p>
          ) : (
            <div className="space-y-4">
              {(riskQ.data ?? []).map((r) => (
                <div
                  key={r.id}
                  className="grid gap-3 rounded-xl border border-border bg-bg-secondary p-4 md:grid-cols-2"
                >
                  <div>
                    <p className="mb-1 text-xs font-medium text-text-secondary">原文</p>
                    <p className="text-sm text-text-primary">{r.original_text}</p>
                    <BadgeInline level={r.risk_level} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-text-secondary">改写</p>
                    <p className="text-sm text-text-primary">{r.rewritten_text}</p>
                    <Button className="mt-2" size="sm" variant="secondary" onClick={() => openRisk(r)}>
                      编辑改写
                    </Button>
                  </div>
                </div>
              ))}
              {(riskQ.data ?? []).length === 0 && (
                <p className="text-sm text-text-secondary">暂无敏感段落记录</p>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <Dialog open={entOpen} onOpenChange={setEntOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>{entEdit ? "编辑实体" : "新增实体"}</DialogTitle>
          <div className="mt-4 space-y-3">
            <Input placeholder="名称" value={fName} onChange={(e) => setFName(e.target.value)} />
            <Input placeholder="标准名" value={fCanon} onChange={(e) => setFCanon(e.target.value)} />
            <Input placeholder="类型 character/location/..." value={fType} onChange={(e) => setFType(e.target.value)} />
            <textarea
              className={cn(fieldClass, "min-h-[72px]")}
              placeholder="描述"
              value={fDesc}
              onChange={(e) => setFDesc(e.target.value)}
            />
            <Input placeholder="别名（逗号分隔）" value={fAliases} onChange={(e) => setFAliases(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEntOpen(false)}>
              取消
            </Button>
            <Button onClick={saveEntity} isLoading={em.create.isPending || em.update.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={relOpen} onOpenChange={setRelOpen}>
        <DialogContent className="max-w-md">
          <DialogTitle>{relEdit ? "编辑关系" : "新增关系"}</DialogTitle>
          <div className="mt-4 space-y-3">
            {!relEdit && (
              <>
                <Input placeholder="实体 A 的 ID" value={rA} onChange={(e) => setRA(e.target.value)} />
                <Input placeholder="实体 B 的 ID" value={rB} onChange={(e) => setRB(e.target.value)} />
              </>
            )}
            <Input placeholder="关系类型" value={rType} onChange={(e) => setRType(e.target.value)} />
            <Input placeholder="描述" value={rDesc} onChange={(e) => setRDesc(e.target.value)} />
            <Input placeholder="置信度 0-1" value={rConf} onChange={(e) => setRConf(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setRelOpen(false)}>
              取消
            </Button>
            <Button onClick={saveRel} isLoading={rm.create.isPending || rm.update.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={tlOpen} onOpenChange={setTlOpen}>
        <DialogContent className="max-w-lg">
          <DialogTitle>{tlEdit ? "编辑时间线事件" : "新增时间线事件"}</DialogTitle>
          <div className="mt-4 space-y-3">
            <textarea
              className={cn(fieldClass, "min-h-[88px]")}
              placeholder="事件描述"
              value={tDesc}
              onChange={(e) => setTDesc(e.target.value)}
            />
            <Input placeholder="排序 order_index" value={tOrder} onChange={(e) => setTOrder(e.target.value)} />
            <Input placeholder="chapter_id（可选）" value={tCh} onChange={(e) => setTCh(e.target.value)} />
            <Input placeholder="scene_id（可选）" value={tSc} onChange={(e) => setTSc(e.target.value)} />
            <Input
              placeholder="参与实体 ID，逗号分隔"
              value={tPart}
              onChange={(e) => setTPart(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setTlOpen(false)}>
              取消
            </Button>
            <Button onClick={saveTl} isLoading={tm.create.isPending || tm.update.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={chOpen} onOpenChange={setChOpen}>
        <DialogContent>
          <DialogTitle>编辑章节</DialogTitle>
          <div className="mt-4 space-y-3">
            <Input placeholder="标题" value={chTitle} onChange={(e) => setChTitle(e.target.value)} />
            <textarea
              className={cn(fieldClass, "min-h-[120px]")}
              placeholder="摘要"
              value={chSum}
              onChange={(e) => setChSum(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setChOpen(false)}>
              取消
            </Button>
            <Button onClick={saveCh} isLoading={csm.updateChapter.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={scOpen}
        onOpenChange={(open) => {
          setScOpen(open);
          if (!open) setScId(null);
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogTitle>编辑场景</DialogTitle>
          {scDetailQ.isLoading ? (
            <p className="mt-4 text-sm text-text-secondary">加载场景正文…</p>
          ) : scDetailQ.isError ? (
            <p className="mt-4 text-sm text-danger">加载失败，请关闭后重试。</p>
          ) : (
            <div className="mt-4 space-y-3">
              <div>
                <p className="mb-1 text-xs font-medium text-text-secondary">正文 raw_text</p>
                <textarea
                  className={cn(fieldClass, "min-h-[200px] font-mono text-xs")}
                  value={scRaw}
                  onChange={(e) => setScRaw(e.target.value)}
                />
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-text-secondary">摘要</p>
                <textarea
                  className={cn(fieldClass, "min-h-[100px]")}
                  value={scSum}
                  onChange={(e) => setScSum(e.target.value)}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="secondary" onClick={() => setScOpen(false)}>
              取消
            </Button>
            <Button
              onClick={saveSc}
              isLoading={csm.updateScene.isPending}
              disabled={scDetailQ.isLoading || scDetailQ.isError}
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={riskOpen} onOpenChange={setRiskOpen}>
        <DialogContent>
          <DialogTitle>编辑改写文本</DialogTitle>
          <textarea
            className={cn(fieldClass, "mt-4 min-h-[160px]")}
            value={riskRw}
            onChange={(e) => setRiskRw(e.target.value)}
          />
          <DialogFooter>
            <Button variant="secondary" onClick={() => setRiskOpen(false)}>
              取消
            </Button>
            <Button onClick={saveRisk} isLoading={riskM.isPending}>
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BadgeInline({ level }: { level: string }) {
  const cls =
    level === "high"
      ? "bg-danger/15 text-danger"
      : level === "medium"
        ? "bg-warning/15 text-warning"
        : "bg-text-secondary/15 text-text-secondary";
  return (
    <span className={cn("mt-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium", cls)}>{level}</span>
  );
}

export default function AdminMetadataPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const raw = searchParams.get("story");
  const parsed = raw ? Number(raw) : NaN;
  const storyId = Number.isFinite(parsed) && parsed > 0 ? parsed : null;

  const { data: stories = [], isLoading } = useAdminStories(false);

  return (
    <div className="p-8">
      <h1 className="font-story text-2xl font-bold text-text-primary">元数据编辑</h1>
      <p className="mt-1 text-sm text-text-secondary">按作品维护实体、关系、时间线与章节（参照 BACKEND_STRUCTURE §2.6）</p>

      <div className="mt-6 max-w-md">
        <label className="mb-1 block text-xs font-medium text-text-secondary">选择作品</label>
        <select
          className={fieldClass}
          value={storyId ?? ""}
          disabled={isLoading}
          onChange={(e) => {
            const v = e.target.value;
            if (v) setSearchParams({ story: v });
            else setSearchParams({});
          }}
        >
          <option value="">— 请选择 —</option>
          {stories.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} {s.title} ({s.status})
            </option>
          ))}
        </select>
      </div>

      {storyId != null && <MetadataEditor storyId={storyId} />}
    </div>
  );
}
