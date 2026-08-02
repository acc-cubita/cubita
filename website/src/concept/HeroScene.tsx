import { Canvas, useFrame } from '@react-three/fiber'
import { Float, RoundedBox } from '@react-three/drei'
import { useEffect, useRef } from 'react'
import * as THREE from 'three'

/**
 * صحنه‌ی سه‌بعدیِ heroِ صفحه‌ی کانسپت — خوشه‌ای از المان‌های حسابداری که شناورند و با
 * ماوس و اسکرول می‌چرخند. عمداً بدونِ HDRI/Environment (که از CDN می‌آید) ساخته شده:
 * فقط نورهای رنگیِ صریح، تا هیچ وابستگیِ بیرونی و هیچ درخواستِ شبکه‌ای نباشد.
 *
 * پرفورمنس: بدونِ سایه، dpr سقف‌دار، و روی موبایل تعدادِ اجسام کمتر (کانواس هم lazy است).
 */

const GOLD = '#f5c542'
const BLUE = '#4f7cff'
const TEAL = '#22d3ee'
const GREEN = '#1f9d74'
const PAPER = '#eef3ff'
const DARK = '#161d2e'

function Coin({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <Float speed={2.2} rotationIntensity={0.7} floatIntensity={1.3}>
      <group position={position} scale={scale} rotation={[Math.PI / 2.4, 0, 0.3]}>
        <mesh>
          <cylinderGeometry args={[0.55, 0.55, 0.12, 48]} />
          <meshStandardMaterial color={GOLD} metalness={0.95} roughness={0.25} emissive="#3a2900" emissiveIntensity={0.35} />
        </mesh>
        <mesh position={[0, 0.07, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.4, 0.03, 12, 40]} />
          <meshStandardMaterial color="#ffe38a" metalness={0.9} roughness={0.3} />
        </mesh>
      </group>
    </Float>
  )
}

function BarChart({ position }: { position: [number, number, number] }) {
  const heights = [0.55, 0.95, 0.75, 1.35, 1.05]
  return (
    <Float speed={1.6} rotationIntensity={0.4} floatIntensity={0.9}>
      <group position={position} rotation={[0, -0.4, 0]}>
        {heights.map((h, i) => (
          <mesh key={i} position={[i * 0.3 - 0.6, h / 2 - 0.2, 0]}>
            <boxGeometry args={[0.22, h, 0.22]} />
            <meshStandardMaterial color={BLUE} metalness={0.5} roughness={0.3} emissive={BLUE} emissiveIntensity={0.45} />
          </mesh>
        ))}
        <mesh position={[0, -0.22, 0]}>
          <boxGeometry args={[1.65, 0.06, 0.45]} />
          <meshStandardMaterial color={DARK} metalness={0.6} roughness={0.4} />
        </mesh>
      </group>
    </Float>
  )
}

function InvoiceCard({ position, rotation }: { position: [number, number, number]; rotation?: [number, number, number] }) {
  return (
    <Float speed={1.9} rotationIntensity={0.5} floatIntensity={1.1}>
      <group position={position} rotation={rotation ?? [0.15, 0.4, -0.12]}>
        <RoundedBox args={[1, 1.35, 0.05]} radius={0.06} smoothness={4}>
          <meshStandardMaterial color={PAPER} metalness={0.1} roughness={0.55} />
        </RoundedBox>
        <mesh position={[0, 0.5, 0.031]}>
          <boxGeometry args={[1, 0.3, 0.01]} />
          <meshStandardMaterial color={BLUE} emissive={BLUE} emissiveIntensity={0.5} />
        </mesh>
        {[0.12, -0.02, -0.16, -0.3, -0.44].map((y, i) => (
          <mesh key={i} position={[-0.12, y, 0.031]}>
            <boxGeometry args={[i % 2 ? 0.5 : 0.72, 0.05, 0.005]} />
            <meshStandardMaterial color="#c4cde0" />
          </mesh>
        ))}
      </group>
    </Float>
  )
}

function Banknote({ position }: { position: [number, number, number] }) {
  return (
    <Float speed={2.4} rotationIntensity={0.9} floatIntensity={1.5}>
      <group position={position} rotation={[0.4, -0.5, 0.15]}>
        <RoundedBox args={[1.3, 0.62, 0.02]} radius={0.04} smoothness={3}>
          <meshStandardMaterial color={GREEN} metalness={0.35} roughness={0.5} emissive="#0e3b2c" emissiveIntensity={0.3} />
        </RoundedBox>
        <mesh position={[0, 0, 0.012]}>
          <circleGeometry args={[0.2, 32]} />
          <meshStandardMaterial color="#7fe3bf" metalness={0.4} roughness={0.4} />
        </mesh>
      </group>
    </Float>
  )
}

function BankCard({ position }: { position: [number, number, number] }) {
  return (
    <Float speed={1.7} rotationIntensity={0.6} floatIntensity={1.0}>
      <group position={position} rotation={[0.2, 0.6, 0.1]}>
        <RoundedBox args={[1.2, 0.75, 0.04]} radius={0.08} smoothness={4}>
          <meshStandardMaterial color="#22304f" metalness={0.85} roughness={0.25} />
        </RoundedBox>
        <mesh position={[-0.32, 0.13, 0.026]}>
          <boxGeometry args={[0.2, 0.15, 0.02]} />
          <meshStandardMaterial color={GOLD} metalness={0.9} roughness={0.3} />
        </mesh>
        <mesh position={[0.1, -0.2, 0.026]}>
          <boxGeometry args={[0.7, 0.08, 0.005]} />
          <meshStandardMaterial color={TEAL} emissive={TEAL} emissiveIntensity={0.4} />
        </mesh>
      </group>
    </Float>
  )
}

function Calculator({ position }: { position: [number, number, number] }) {
  const btns = []
  for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) btns.push([c * 0.19 - 0.19, -0.05 - r * 0.19, 0.08] as [number, number, number])
  return (
    <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.9}>
      <group position={position} rotation={[0.1, -0.5, -0.1]}>
        <RoundedBox args={[0.78, 1.02, 0.14]} radius={0.05} smoothness={4}>
          <meshStandardMaterial color="#131a2a" metalness={0.5} roughness={0.5} />
        </RoundedBox>
        <mesh position={[0, 0.34, 0.075]}>
          <boxGeometry args={[0.58, 0.22, 0.01]} />
          <meshStandardMaterial color="#04121a" emissive={TEAL} emissiveIntensity={0.9} />
        </mesh>
        {btns.map((p, i) => (
          <mesh key={i} position={p}>
            <boxGeometry args={[0.14, 0.14, 0.03]} />
            <meshStandardMaterial color={i === 11 ? BLUE : '#2a3450'} emissive={i === 11 ? BLUE : '#000'} emissiveIntensity={i === 11 ? 0.5 : 0} metalness={0.4} roughness={0.5} />
          </mesh>
        ))}
      </group>
    </Float>
  )
}

function Safe({ position }: { position: [number, number, number] }) {
  return (
    <Float speed={1.3} rotationIntensity={0.35} floatIntensity={0.7}>
      <group position={position} rotation={[0.15, 0.5, 0]}>
        <RoundedBox args={[1.05, 1.05, 0.7]} radius={0.06} smoothness={4}>
          <meshStandardMaterial color="#232d44" metalness={0.7} roughness={0.35} />
        </RoundedBox>
        <RoundedBox args={[0.78, 0.82, 0.06]} radius={0.04} position={[0, 0, 0.36]}>
          <meshStandardMaterial color="#2c3855" metalness={0.75} roughness={0.3} />
        </RoundedBox>
        <mesh position={[0.14, 0, 0.42]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.15, 0.045, 16, 32]} />
          <meshStandardMaterial color={GOLD} metalness={0.95} roughness={0.25} />
        </mesh>
        <mesh position={[0.14, 0, 0.42]}>
          <cylinderGeometry args={[0.05, 0.05, 0.1, 20]} />
          <meshStandardMaterial color="#ffe38a" metalness={0.9} roughness={0.3} />
        </mesh>
      </group>
    </Float>
  )
}

function Check({ position }: { position: [number, number, number] }) {
  return (
    <Float speed={2.1} rotationIntensity={0.8} floatIntensity={1.4}>
      <group position={position} rotation={[0.3, 0.5, 0.1]}>
        <RoundedBox args={[1.35, 0.62, 0.02]} radius={0.03} smoothness={3}>
          <meshStandardMaterial color="#f2f7f2" metalness={0.1} roughness={0.6} />
        </RoundedBox>
        <mesh position={[0, 0.22, 0.012]}>
          <boxGeometry args={[1.35, 0.14, 0.005]} />
          <meshStandardMaterial color={GREEN} emissive={GREEN} emissiveIntensity={0.35} />
        </mesh>
        {[-0.02, -0.16].map((y, i) => (
          <mesh key={i} position={[-0.2, y, 0.012]}>
            <boxGeometry args={[0.8, 0.045, 0.005]} />
            <meshStandardMaterial color="#b9c6bb" />
          </mesh>
        ))}
      </group>
    </Float>
  )
}

function Cluster({ scrollRef, reduced }: { scrollRef: React.MutableRefObject<number>; reduced: boolean }) {
  const group = useRef<THREE.Group>(null!)
  const auto = useRef(0)
  useFrame((state, delta) => {
    const g = group.current
    if (!g) return
    auto.current += delta * (reduced ? 0 : 0.14)
    const s = scrollRef.current
    g.rotation.y = auto.current + s * Math.PI * 0.8
    g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, state.pointer.y * -0.22 + s * 0.3, 0.06)
    g.position.y = THREE.MathUtils.lerp(g.position.y, -s * 1.6, 0.08)
  })
  return (
    <group ref={group}>
      <Coin position={[-2.1, 1.1, 0.5]} scale={0.95} />
      <Coin position={[2.3, 1.4, -0.6]} scale={0.7} />
      <Coin position={[1.6, -1.5, 0.8]} scale={0.55} />
      <BarChart position={[2.1, -0.4, 0]} />
      <InvoiceCard position={[-2.2, -0.6, 0.2]} />
      <Banknote position={[0.2, 1.9, -0.3]} />
      <BankCard position={[-1.4, 0.4, 1.1]} />
      <Calculator position={[1.2, 0.9, 0.9]} />
      <Safe position={[-0.3, -1.6, -0.4]} />
      <Check position={[0.6, -0.3, 1.4]} />
    </group>
  )
}

export default function HeroScene() {
  const scrollRef = useRef(0)
  const reduced = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    const onScroll = () => {
      const p = Math.min(1, Math.max(0, window.scrollY / (window.innerHeight || 800)))
      scrollRef.current = p
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <Canvas
      camera={{ position: [0, 0, 7.5], fov: 42 }}
      dpr={[1, 1.8]}
      gl={{ antialias: true, alpha: true }}
      style={{ width: '100%', height: '100%' }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 5, 6]} intensity={1.1} color="#ffffff" />
      <pointLight position={[-6, 2, 3]} intensity={60} color={BLUE} distance={20} />
      <pointLight position={[6, -3, 2]} intensity={45} color={GOLD} distance={20} />
      <pointLight position={[0, 4, -4]} intensity={40} color={TEAL} distance={20} />
      <Cluster scrollRef={scrollRef} reduced={reduced} />
    </Canvas>
  )
}
