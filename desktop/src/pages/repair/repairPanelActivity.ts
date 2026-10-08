import {createContext,useContext} from 'react'
export const RepairPanelActive=createContext(true)
export const useRepairPanelActive=()=>useContext(RepairPanelActive)
