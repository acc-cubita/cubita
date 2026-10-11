// @vitest-environment jsdom
import {act,useEffect,useState} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {RepairRetainedPanel,RepairWorkspaceTabs} from './RepairWorkspaceTabs'
import {useRepairPanelActive} from './repairPanelActivity'
import {useRepairDraftGuard} from './useRepairDraftGuard'
import {RepairDraftContext,useRepairDraftMarker} from './repairDraftContext'
import {JalaliDatePicker} from '../../components/JalaliDatePicker'

let container:HTMLDivElement,root:Root
beforeEach(()=>{(globalThis as Record<string,unknown>).IS_REACT_ACT_ENVIRONMENT=true;container=document.createElement('div');document.body.append(container);root=createRoot(container)})
afterEach(()=>{act(()=>root.unmount());container.remove();vi.restoreAllMocks()})
const click=(selector:string)=>act(()=>container.querySelector<HTMLButtonElement>(selector)!.click())

describe('repair workspace drafts and navigation',()=>{
 it('loads sections only when opened, retains drafts and pauses inactive effects',()=>{
  const activity:string[]=[]
  function Editor({name}:{name:string}){const active=useRepairPanelActive(),[value,setValue]=useState('');useEffect(()=>{if(active)activity.push(name)},[active,name]);return <input aria-label={name} value={value} onChange={e=>setValue(e.target.value)}/>}
  function Host(){const [tab,setTab]=useState('summary');return <><RepairWorkspaceTabs label="case" value={tab} onChange={setTab} tabs={[{id:'summary',label:'پذیرش'},{id:'repair',label:'تعمیر'}]}/><RepairRetainedPanel active={tab==='summary'}><Editor name="summary"/></RepairRetainedPanel><RepairRetainedPanel active={tab==='repair'}><Editor name="repair"/></RepairRetainedPanel></>}
  act(()=>root.render(<Host/>));expect(activity).toEqual(['summary']);expect(container.querySelector('[aria-label=repair]')).toBeNull()
  const input=container.querySelector<HTMLInputElement>('[aria-label=summary]')!
  act(()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'پیش‌نویس پذیرش');input.dispatchEvent(new Event('input',{bubbles:true}))})
  click('[role=tab]:last-child');expect(activity).toEqual(['summary','repair']);expect(input.closest('[role=tabpanel]')?.hasAttribute('hidden')).toBe(true)
  click('[role=tab]:first-child');expect(input.value).toBe('پیش‌نویس پذیرش');expect(activity).toEqual(['summary','repair','summary'])
 })
 it('supports keyboard tab navigation with one focusable tab',()=>{
  function Host(){const [value,setValue]=useState('a');return <RepairWorkspaceTabs label="sections" value={value} onChange={setValue} tabs={[{id:'a',label:'اول'},{id:'b',label:'دوم'}]}/>}
  act(()=>root.render(<Host/>));const first=container.querySelector<HTMLButtonElement>('[role=tab]')!
  act(()=>first.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true})))
  const active=container.querySelector<HTMLButtonElement>('[aria-selected=true]')!
  expect(active.textContent).toBe('دوم');expect(document.activeElement).toBe(active);expect(container.querySelectorAll('[role=tab][tabindex="0"]')).toHaveLength(1)
 })
 it('marks custom picker changes from their focused trigger without browser persistence',()=>{
  let guard:(()=>boolean)|null=null,choose:()=>void=()=>{}
  const register=(value:(()=>boolean)|null)=>{guard=value}
  function Picker(){const mark=useRepairDraftMarker();choose=mark;return <button id="picker">انتخابگر</button>}
  function Host(){const draft=useRepairDraftGuard(register);return <RepairDraftContext.Provider value={draft.mark}><div ref={draft.root} data-repair-draft onFocusCapture={event=>draft.focus(event.target)}><Picker/></div></RepairDraftContext.Provider>}
  act(()=>root.render(<Host/>));const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
  act(()=>container.querySelector<HTMLButtonElement>('#picker')!.focus());act(()=>choose());expect(guard!()).toBe(false);expect(confirm).toHaveBeenCalledOnce()
 })
 it('keeps a date-only edit dirty after the real calendar popup disappears',()=>{
  let guard:(()=>boolean)|null=null
  const register=(value:(()=>boolean)|null)=>{guard=value}
  function Editor(){const mark=useRepairDraftMarker(),[value,setValue]=useState('');return <JalaliDatePicker value={value} onChange={value=>{mark();setValue(value)}}/>}
  function Host(){const draft=useRepairDraftGuard(register);return <RepairDraftContext.Provider value={draft.mark}><div ref={draft.root} data-repair-draft onFocusCapture={event=>draft.focus(event.target)}><Editor/></div></RepairDraftContext.Provider>}
  act(()=>root.render(<Host/>));vi.spyOn(window,'confirm').mockReturnValue(false)
  const trigger=container.querySelector<HTMLButtonElement>('.jalali-date-trigger')!;act(()=>{trigger.focus();trigger.click()})
  const today=[...container.querySelectorAll<HTMLButtonElement>('[role=dialog] button')].find(button=>button.textContent?.trim()==='امروز')!
  act(()=>{today.focus();today.click()});expect(container.querySelector('[role=dialog]')).toBeNull();expect(guard!()).toBe(false)
 })
 it('blocks exit and unload for dirty forms without clearing another form on save',()=>{
  let guard:(()=>boolean)|null=null,save:(scope:Element|null)=>void=()=>{}
  const register=(value:(()=>boolean)|null)=>{guard=value}
  function Host(){const draft=useRepairDraftGuard(register);save=draft.saved;return <div ref={draft.root} data-repair-draft onChangeCapture={draft.change}><form id="first"><input aria-label="one"/></form><form id="second"><input aria-label="two"/></form></div>}
  act(()=>root.render(<Host/>));const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
  act(()=>{for(const name of ['one','two']){const input=container.querySelector('[aria-label='+name+']')!;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'unsaved');input.dispatchEvent(new Event('input',{bubbles:true}))}})
  expect(guard!()).toBe(false);expect(confirm).toHaveBeenCalledTimes(1)
  const unload=new Event('beforeunload',{cancelable:true});window.dispatchEvent(unload);expect(unload.defaultPrevented).toBe(true)
  save(container.querySelector('#first'));expect(guard!()).toBe(false)
  save(container.querySelector('#second'));expect(guard!()).toBe(true)
 })
})
