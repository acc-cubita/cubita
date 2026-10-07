import {createContext,useContext} from 'react'
export const RepairDraftContext=createContext<()=>void>(()=>{})
export const useRepairDraftMarker=()=>useContext(RepairDraftContext)
