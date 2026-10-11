// @vitest-environment jsdom
import {act,createElement} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,expect,it,vi} from 'vitest'
import {useListingDraft,type ListingDraft} from './listingDraft'
import * as api from '../api'

vi.mock('../api',()=>({createMpListing:vi.fn(),updateMpListing:vi.fn()}))
let root:Root|undefined
let container:HTMLDivElement|undefined
afterEach(()=>{if(root) act(()=>root!.unmount());container?.remove();vi.clearAllMocks()})
it('keeps eight-decimal pack quantity and its local measurement intact on submission',async()=>{
  ;(globalThis as Record<string,unknown>).IS_REACT_ACT_ENVIRONMENT=true
  let draft:ListingDraft
  function Harness(){draft=useListingDraft({token:'local',onSaved:()=>{}});return null}
  container=document.createElement('div');document.body.append(container);root=createRoot(container)
  await act(async()=>root!.render(createElement(Harness)))
  await act(async()=>draft!.setForm(previous=>({...previous,kind:'pack',title:'پک آزمون',
    components:[{itemId:'cloth',qty:'1234567890123456.12345678',unitId:'kg',baseQtyPreview:'150',
      observations:[{rule_id:'actual',from_qty:'36.12345678',to_qty:'150.87654321'}]}]})))
  await act(async()=>{expect(await draft!.submit()).toBe(true)})
  expect(api.createMpListing).toHaveBeenCalledWith('local',expect.objectContaining({
    components:[{item_id:'cloth',qty:'1234567890123456.12345678',unit_id:'kg',
      observations:[{rule_id:'actual',from_qty:'36.12345678',to_qty:'150.87654321'}]}]}))
})
